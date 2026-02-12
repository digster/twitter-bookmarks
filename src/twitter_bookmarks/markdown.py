"""Render Bookmark objects into a single markdown file.

Output is a chronologically ordered (newest first) markdown file
with bookmarks grouped by date.
"""

from datetime import datetime
from urllib.parse import urlparse

from .models import Bookmark


def render_bookmarks_file(bookmarks: list[Bookmark]) -> str:
    """Render a complete bookmarks.md file."""
    if not bookmarks:
        return "# Twitter/X Bookmarks\n\n*No bookmarks found.*\n"

    sorted_bookmarks = sorted(
        bookmarks, key=lambda b: b.created_at, reverse=True
    )

    lines = [
        "# Twitter/X Bookmarks",
        "",
        (
            f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            f" | {len(sorted_bookmarks)} bookmarks*"
        ),
        "",
    ]

    current_date: str | None = None
    for bookmark in sorted_bookmarks:
        date_str = bookmark.created_at.strftime("%B %d, %Y")
        if date_str != current_date:
            current_date = date_str
            lines.append(f"## {date_str}")
            lines.append("")

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
