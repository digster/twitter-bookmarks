"""Parse Twitter GraphQL API responses into Bookmark model objects.

The GraphQL response nests tweet data deeply:
    entry -> content -> itemContent -> tweet_results -> result

Each result may be wrapped in a TweetWithVisibilityResults container.
"""

import logging
from datetime import datetime

from .models import Bookmark, MediaItem, User

logger = logging.getLogger(__name__)

# Twitter's date format: "Thu May 14 18:01:35 +0000 2020"
TWITTER_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"


def parse_bookmarks(raw_entries: list[dict]) -> list[Bookmark]:
    """Parse a list of raw GraphQL entry dicts into Bookmark objects."""
    bookmarks = []
    for entry in raw_entries:
        try:
            bookmark = _parse_single_entry(entry)
            if bookmark:
                bookmarks.append(bookmark)
        except (KeyError, TypeError, ValueError) as e:
            entry_id = entry.get("entryId", "?")
            logger.warning("Skipping malformed entry %s: %s", entry_id, e)
    return bookmarks


def _parse_single_entry(entry: dict) -> Bookmark | None:
    """Parse a single timeline entry into a Bookmark."""
    tweet_result = (
        entry.get("content", {})
        .get("itemContent", {})
        .get("tweet_results", {})
        .get("result", {})
    )

    if not tweet_result:
        return None

    # Unwrap TweetWithVisibilityResults wrapper
    if tweet_result.get("__typename") == "TweetWithVisibilityResults":
        tweet_result = tweet_result.get("tweet", {})

    if not tweet_result or tweet_result.get("__typename") == "TweetTombstone":
        return None

    tweet_id = tweet_result.get("rest_id", "")
    legacy = tweet_result.get("legacy", {})
    core = tweet_result.get("core", {})

    # Parse user
    user_result = core.get("user_results", {}).get("result", {})
    user_legacy = user_result.get("legacy", {})
    author = User(
        id=user_result.get("rest_id", ""),
        username=user_legacy.get("screen_name", "unknown"),
        display_name=user_legacy.get("name", "Unknown"),
    )

    # Parse text — replace t.co URLs with expanded versions
    full_text = legacy.get("full_text", "")
    entities = legacy.get("entities", {})
    full_text = _expand_urls_in_text(full_text, entities.get("urls", []))

    # Remove t.co media URLs from text (they appear at the end)
    for media_entity in entities.get("media", []):
        media_url = media_entity.get("url", "")
        if media_url:
            full_text = full_text.replace(media_url, "").strip()

    # Parse timestamp
    created_at_str = legacy.get("created_at", "")
    created_at = datetime.strptime(created_at_str, TWITTER_DATE_FORMAT)

    # Parse external URLs
    urls = [
        u["expanded_url"]
        for u in entities.get("urls", [])
        if "expanded_url" in u
    ]

    # Parse media
    media_entities = legacy.get("extended_entities", {}).get("media", [])
    if not media_entities:
        media_entities = entities.get("media", [])
    media = [
        MediaItem(
            type=m.get("type", "photo"),
            url=m.get("media_url_https", ""),
            expanded_url=m.get("expanded_url", ""),
        )
        for m in media_entities
    ]

    # Quote tweet detection
    quoted_tweet_url = None
    if legacy.get("is_quote_status"):
        quoted_result = (
            tweet_result.get("quoted_status_result", {}).get("result", {})
        )
        quoted_user = (
            quoted_result.get("core", {})
            .get("user_results", {})
            .get("result", {})
            .get("legacy", {})
        )
        quoted_id = quoted_result.get("rest_id")
        quoted_screen_name = quoted_user.get("screen_name")
        if quoted_screen_name and quoted_id:
            quoted_tweet_url = (
                f"https://x.com/{quoted_screen_name}/status/{quoted_id}"
            )

    tweet_url = f"https://x.com/{author.username}/status/{tweet_id}"

    return Bookmark(
        tweet_id=tweet_id,
        author=author,
        text=full_text,
        created_at=created_at,
        tweet_url=tweet_url,
        urls=urls,
        media=media,
        is_reply=bool(legacy.get("in_reply_to_screen_name")),
        reply_to_user=legacy.get("in_reply_to_screen_name"),
        is_quote=legacy.get("is_quote_status", False),
        quoted_tweet_url=quoted_tweet_url,
        lang=legacy.get("lang", "en"),
    )


def _expand_urls_in_text(text: str, url_entities: list[dict]) -> str:
    """Replace t.co shortened URLs in text with their expanded versions."""
    # Sort by index descending so replacements don't shift positions
    sorted_entities = sorted(
        url_entities,
        key=lambda u: u.get("indices", [0])[0],
        reverse=True,
    )
    for entity in sorted_entities:
        short_url = entity.get("url", "")
        expanded = entity.get("expanded_url", short_url)
        text = text.replace(short_url, expanded)
    return text
