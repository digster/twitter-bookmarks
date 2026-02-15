"""Convert Bookmark objects to CSV format."""

import csv
import io
from typing import TextIO

from .models import Bookmark

CSV_COLUMNS = [
    "tweet_id",
    "username",
    "display_name",
    "text",
    "date",
    "tweet_url",
    "links",
    "media_urls",
    "media_types",
    "is_reply",
    "reply_to_user",
    "is_quote",
    "quoted_tweet_url",
]


def bookmarks_to_csv(bookmarks: list[Bookmark], output: TextIO | None = None) -> str:
    """Convert bookmarks to CSV format.

    Args:
        bookmarks: List of Bookmark objects to convert.
        output: Optional file-like object to write to. If None, returns CSV as string.

    Returns:
        CSV content as a string (also written to output if provided).
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()

    for b in bookmarks:
        writer.writerow(
            {
                "tweet_id": b.tweet_id,
                "username": b.author.username,
                "display_name": b.author.display_name,
                "text": b.text,
                "date": b.created_at.isoformat() if b.created_at else "",
                "tweet_url": b.tweet_url,
                "links": "|".join(b.urls) if b.urls else "",
                "media_urls": (
                    "|".join(m.url for m in b.media) if b.media else ""
                ),
                "media_types": (
                    "|".join(m.type for m in b.media) if b.media else ""
                ),
                "is_reply": "true" if b.is_reply else "false",
                "reply_to_user": b.reply_to_user or "",
                "is_quote": "true" if b.is_quote else "false",
                "quoted_tweet_url": b.quoted_tweet_url or "",
            }
        )

    result = buf.getvalue()
    if output is not None:
        output.write(result)
    return result
