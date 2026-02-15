"""Render Bookmark objects into a single markdown file.

Output is a chronologically ordered (newest first) markdown file.
No header lines or date-group headers — just bookmark entries separated by ---.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from .models import Bookmark


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
