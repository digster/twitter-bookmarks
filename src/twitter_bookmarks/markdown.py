"""Render and parse Bookmark objects to/from a markdown file.

Output is a chronologically ordered (newest first) markdown file.
No header lines or date-group headers — just bookmark entries separated by ---.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from .models import Bookmark, MediaItem, User


def render_bookmarks_file(bookmarks: list[Bookmark]) -> str:
    """Render a complete bookmarks.md file (all bookmarks, newest first)."""
    if not bookmarks:
        return ""

    sorted_bookmarks = sorted(
        bookmarks, key=lambda b: b.created_at, reverse=True
    )

    lines: list[str] = []
    for bookmark in sorted_bookmarks:
        lines.append(_render_single_bookmark(bookmark))
        lines.append("")

    return "\n".join(lines)


def _render_single_bookmark(bookmark: Bookmark) -> str:
    """Render a single bookmark entry."""
    lines: list[str] = []

    # Header with author
    lines.append(f"### @{bookmark.author.username}")
    if bookmark.author.display_name != bookmark.author.username:
        lines.append(f"*{bookmark.author.display_name}*")
    lines.append("")

    # Tweet text as blockquote
    text_lines = bookmark.text.strip().split("\n")
    for text_line in text_lines:
        lines.append(f"> {text_line}")
    lines.append("")

    # Metadata
    lines.append(
        f"- **Tweet:** [{bookmark.tweet_url}]({bookmark.tweet_url})"
    )
    lines.append(
        f"- **Date:** {bookmark.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    lines.append(f"- **ID:** {bookmark.tweet_id}")

    if bookmark.urls:
        url_links = ", ".join(
            f"[{_shorten_url(u)}]({u})" for u in bookmark.urls
        )
        lines.append(f"- **Links:** {url_links}")

    if bookmark.media:
        media_desc = ", ".join(
            f"[{m.type}]({m.url})" for m in bookmark.media
        )
        lines.append(f"- **Media:** {media_desc}")

    if bookmark.is_reply and bookmark.reply_to_user:
        lines.append(f"- **Reply to:** @{bookmark.reply_to_user}")

    if bookmark.is_quote and bookmark.quoted_tweet_url:
        lines.append(
            f"- **Quote of:** [{bookmark.quoted_tweet_url}]"
            f"({bookmark.quoted_tweet_url})"
        )

    lines.append("")
    lines.append("---")

    return "\n".join(lines)


def _shorten_url(url: str) -> str:
    """Shorten a URL for display (domain + truncated path)."""
    parsed = urlparse(url)
    display = parsed.netloc + parsed.path
    if len(display) > 60:
        display = display[:57] + "..."
    return display


# ── Markdown-as-source-of-truth helpers ─────────────────────────


def strip_legacy_headers(content: str) -> str:
    """Strip old-format header lines from existing markdown content.

    Removes: # Twitter/X Bookmarks, *Last updated...*, ## Month Day, Year,
    *No bookmarks found.* — so the content can be cleanly prepended to.
    """
    lines = content.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# Twitter/X Bookmarks"):
            continue
        if stripped.startswith("*Last updated:") or stripped.startswith(
            "*last updated:"
        ):
            continue
        if stripped == "*No bookmarks found.*":
            continue
        if re.match(r"^## [A-Z][a-z]+ \d{1,2}, \d{4}$", stripped):
            continue
        cleaned.append(line)

    # Remove leading blank lines
    while cleaned and cleaned[0].strip() == "":
        cleaned.pop(0)

    return "\n".join(cleaned)


def extract_ids_from_markdown(content: str) -> set[str]:
    """Extract tweet IDs from markdown content.

    Checks for `- **ID:** {id}` lines first, falls back to
    `- **Tweet:** ...status/{id}...` URLs for backward compat.
    """
    ids: set[str] = set()

    # Primary: explicit ID lines
    for match in re.finditer(r"^- \*\*ID:\*\*\s+(\S+)", content, re.MULTILINE):
        ids.add(match.group(1))

    # Fallback: extract from tweet URLs if no ID lines found
    if not ids:
        for match in re.finditer(
            r"^- \*\*Tweet:\*\*.*?/status/(\d+)", content, re.MULTILINE
        ):
            ids.add(match.group(1))

    return ids


def parse_markdown_to_bookmarks(content: str) -> list[Bookmark]:
    """Parse a bookmarks markdown file back into Bookmark objects.

    This is the inverse of render_bookmarks_file(). It uses a line-by-line
    state machine that mirrors the JS parser in viewer.html.

    Lossy fields (not stored in markdown):
        User.id → "", Bookmark.lang → "en", MediaItem.expanded_url → ""
    """
    if not content or not content.strip():
        return []

    content = strip_legacy_headers(content)
    lines = content.split("\n")
    bookmarks: list[Bookmark] = []

    # Current bookmark state
    username: str = ""
    display_name: str = ""
    text_lines: list[str] = []
    tweet_url: str = ""
    date: datetime | None = None
    tweet_id: str = ""
    urls: list[str] = []
    media: list[MediaItem] = []
    is_reply: bool = False
    reply_to_user: str | None = None
    is_quote: bool = False
    quoted_tweet_url: str | None = None
    in_entry: bool = False

    link_re = re.compile(r"\[([^\]]*)\]\((https?://[^)]+)\)")
    media_re = re.compile(r"\[(photo|video|animated_gif)\]\((https?://[^)]+)\)")

    def _finalize() -> None:
        nonlocal in_entry, username, display_name, text_lines
        nonlocal tweet_url, date, tweet_id, urls, media
        nonlocal is_reply, reply_to_user, is_quote, quoted_tweet_url

        if not in_entry or not username:
            return

        bookmarks.append(
            Bookmark(
                tweet_id=tweet_id,
                author=User(
                    id="",
                    username=username,
                    display_name=display_name or username,
                ),
                text="\n".join(text_lines),
                created_at=date or datetime(1970, 1, 1, tzinfo=timezone.utc),
                tweet_url=tweet_url,
                urls=urls,
                media=media,
                is_reply=is_reply,
                reply_to_user=reply_to_user,
                is_quote=is_quote,
                quoted_tweet_url=quoted_tweet_url,
                lang="en",
            )
        )

        # Reset state
        username = ""
        display_name = ""
        text_lines = []
        tweet_url = ""
        date = None
        tweet_id = ""
        urls = []
        media = []
        is_reply = False
        reply_to_user = None
        is_quote = False
        quoted_tweet_url = None
        in_entry = False

    for line in lines:
        # Username header — starts a new entry
        if line.startswith("### @"):
            # Finalize previous entry if not terminated by ---
            if in_entry:
                _finalize()
            username = line[5:].strip()
            in_entry = True
            continue

        if not in_entry:
            continue

        # Display name — *Name* (only if we haven't captured one yet)
        if (
            not display_name
            and line.startswith("*")
            and line.endswith("*")
            and len(line) > 2
            and not line.startswith("*Last")
        ):
            display_name = line[1:-1].strip()
            continue

        # Blockquote text
        if line.startswith("> ") or line == ">":
            text_lines.append(line[2:] if line.startswith("> ") else "")
            continue

        # Metadata fields
        if line.startswith("- **Tweet:**"):
            m = link_re.search(line)
            if m:
                tweet_url = m.group(2)
            continue

        if line.startswith("- **Date:**"):
            date_str = line[11:].strip()
            try:
                date = datetime.strptime(
                    date_str, "%Y-%m-%d %H:%M UTC"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                date = None
            continue

        if line.startswith("- **ID:**"):
            tweet_id = line[9:].strip()
            continue

        if line.startswith("- **Links:**"):
            urls = [m.group(2) for m in link_re.finditer(line)]
            continue

        if line.startswith("- **Media:**"):
            media = [
                MediaItem(type=m.group(1), url=m.group(2), expanded_url="")
                for m in media_re.finditer(line)
            ]
            continue

        if line.startswith("- **Reply to:**"):
            is_reply = True
            reply_to_user = line[15:].strip().lstrip("@")
            continue

        if line.startswith("- **Quote of:**"):
            is_quote = True
            m = link_re.search(line)
            if m:
                quoted_tweet_url = m.group(2)
            continue

        # Separator — finalize current entry
        if line == "---":
            _finalize()
            continue

    # Finalize last entry if file doesn't end with ---
    if in_entry:
        _finalize()

    return bookmarks


def extract_latest_date(content: str) -> datetime | None:
    """Extract the date from the first **Date:** line (newest bookmark).

    Returns a timezone-aware datetime or None if not found.
    """
    match = re.search(
        r"\*\*Date:\*\*\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+UTC",
        content,
    )
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
