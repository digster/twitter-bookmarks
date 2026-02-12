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


def _extract_user(tweet_result: dict, tweet_id: str = "") -> User:
    """Extract user data from a tweet result, trying multiple known key paths.

    Twitter's GraphQL schema evolves — the user object may be nested under
    different keys depending on the API version. We try paths in order of
    likelihood and fall back to a recursive search as a last resort.
    """
    core = tweet_result.get("core", {})
    logger.debug(
        "tweet %s: tweet_result keys=%s, core keys=%s",
        tweet_id,
        list(tweet_result.keys()),
        list(core.keys()),
    )

    # Path 1: standard — core.user_results.result.legacy
    user_results = core.get("user_results", {})
    if user_results:
        logger.debug("tweet %s: user_results keys=%s", tweet_id, list(user_results.keys()))
        result = user_results.get("result", {})
        if result:
            legacy = result.get("legacy", {})
            if legacy and legacy.get("screen_name"):
                logger.debug("tweet %s: resolved via user_results.result.legacy", tweet_id)
                return User(
                    id=result.get("rest_id", ""),
                    username=legacy["screen_name"],
                    display_name=legacy.get("name", "Unknown"),
                )
            # Path 3: flattened — screen_name directly on result (no legacy wrapper)
            if result.get("screen_name"):
                logger.debug("tweet %s: resolved via user_results.result (flattened)", tweet_id)
                return User(
                    id=result.get("rest_id", ""),
                    username=result["screen_name"],
                    display_name=result.get("name", "Unknown"),
                )

    # Path 2: singular variant — core.user_result.result.legacy
    user_result_singular = core.get("user_result", {})
    if user_result_singular:
        logger.debug("tweet %s: trying singular user_result", tweet_id)
        result = user_result_singular.get("result", {})
        if result:
            legacy = result.get("legacy", {})
            if legacy and legacy.get("screen_name"):
                logger.debug("tweet %s: resolved via user_result.result.legacy", tweet_id)
                return User(
                    id=result.get("rest_id", ""),
                    username=legacy["screen_name"],
                    display_name=legacy.get("name", "Unknown"),
                )
            if result.get("screen_name"):
                logger.debug("tweet %s: resolved via user_result.result (flattened)", tweet_id)
                return User(
                    id=result.get("rest_id", ""),
                    username=result["screen_name"],
                    display_name=result.get("name", "Unknown"),
                )

    # Path 4: deep search — walk the tree looking for a user-like dict
    found = _deep_find_user(core)
    if found:
        logger.debug("tweet %s: resolved via deep search", tweet_id)
        return User(
            id=found.get("rest_id", ""),
            username=found["screen_name"],
            display_name=found.get("name", "Unknown"),
        )

    logger.warning(
        "tweet %s: could not resolve username — all paths returned empty. "
        "core keys: %s. Use --dump-raw to inspect the API response.",
        tweet_id,
        list(core.keys()),
    )
    return User(id="", username="unknown", display_name="Unknown")


def _deep_find_user(obj: object, max_depth: int = 6) -> dict | None:
    """Recursively search for a dict containing both 'screen_name' and 'name'.

    Walks nested dicts/lists up to max_depth levels. Returns the first match.
    """
    if max_depth <= 0 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, dict):
        if "screen_name" in obj and "name" in obj:
            return obj
        for value in obj.values():
            found = _deep_find_user(value, max_depth - 1)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find_user(item, max_depth - 1)
            if found:
                return found
    return None


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

    # Parse user via resilient multi-path extraction
    author = _extract_user(tweet_result, tweet_id)

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
        quoted_id = quoted_result.get("rest_id")
        quoted_user = _extract_user(quoted_result, f"quoted-{quoted_id}")
        if quoted_user.username != "unknown" and quoted_id:
            quoted_tweet_url = (
                f"https://x.com/{quoted_user.username}/status/{quoted_id}"
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
