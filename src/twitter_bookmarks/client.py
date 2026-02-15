"""Twitter GraphQL API client for fetching bookmarks.

Authentication uses cookie-based auth (auth_token + ct0) matching Twitter's
web client behavior. The bearer token is a static, public token embedded in
Twitter's web client JS — all web clients share the same one.

The query ID and feature flags are hardcoded and may need updating when
Twitter deploys changes. Override with environment variables if needed:
    TWITTER_BOOKMARKS_QUERY_ID
    TWITTER_BEARER_TOKEN
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Static bearer token used by Twitter's web client (public, not a user secret)
BEARER_TOKEN = os.environ.get(
    "TWITTER_BEARER_TOKEN",
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
)

# GraphQL query ID for Bookmarks — rotates every few weeks
BOOKMARKS_QUERY_ID = os.environ.get(
    "TWITTER_BOOKMARKS_QUERY_ID",
    "pLtjrO4ubNh996M_Cubwsg",
)

# Feature flags sent with each request — must match current Twitter web client
# Reference: https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/twitter.py
BOOKMARKS_FEATURES = {
    "rweb_video_screen_enabled": False,
    "payments_enabled": False,
    "rweb_xchat_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "responsive_web_grok_show_grok_translated_post": False,
    "responsive_web_grok_analysis_button_from_backend": True,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}


@dataclass
class BookmarksPage:
    """A single page of bookmark results."""

    entries: list[dict] = field(default_factory=list)
    cursor_top: str | None = None
    cursor_bottom: str | None = None


class TwitterClient:
    """Client for Twitter's internal GraphQL API using cookie auth."""

    def __init__(
        self,
        auth_token: str,
        ct0: str,
        query_id: str | None = None,
        capture_raw: bool = False,
    ):
        self._query_id = query_id or BOOKMARKS_QUERY_ID
        self._graphql_url = (
            f"https://x.com/i/api/graphql/{self._query_id}/Bookmarks"
        )
        self._capture_raw = capture_raw
        self.raw_responses: list[dict] = []
        self._client = httpx.Client(
            headers={
                "authorization": f"Bearer {BEARER_TOKEN}",
                "x-csrf-token": ct0,
                "x-twitter-active-user": "yes",
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-client-language": "en",
                "content-type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
            cookies={"auth_token": auth_token, "ct0": ct0},
            timeout=30.0,
            follow_redirects=True,
        )

    def fetch_bookmarks_page(
        self, count: int = 20, cursor: str | None = None
    ) -> BookmarksPage:
        """Fetch a single page of bookmarks."""
        variables: dict = {"count": count, "includePromotedContent": False}
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(BOOKMARKS_FEATURES),
        }

        response = self._client.get(self._graphql_url, params=params)

        if response.status_code == 429:
            reset_time = response.headers.get("x-rate-limit-reset")
            wait_msg = ""
            if reset_time:
                wait_seconds = int(reset_time) - int(time.time())
                if wait_seconds > 0:
                    wait_msg = f" Retry in {wait_seconds}s."
            raise RuntimeError(f"Rate limited by Twitter.{wait_msg}")

        if response.status_code == 400:
            raise RuntimeError(
                "Bad request (400). The feature flags or query parameters "
                "may be outdated.\n"
                "Try updating the query ID with: "
                "`twitter-bookmarks setup --query-id-only`\n"
                "If the problem persists, the feature flags in client.py "
                "need updating to match the current Twitter web client."
            )

        if response.status_code == 404:
            raise RuntimeError(
                "GraphQL query ID is stale (404). Twitter rotates these "
                "periodically.\n"
                "To fix: open x.com/i/bookmarks in your browser, open "
                "DevTools → Network, filter for 'Bookmarks', and copy the "
                "query ID from the request URL "
                "(between /graphql/ and /Bookmarks).\n"
                "Then either:\n"
                "  • Set TWITTER_BOOKMARKS_QUERY_ID=<new_id> env var, or\n"
                "  • Run `twitter-bookmarks setup` to update it."
            )

        if response.status_code in (401, 403):
            raise RuntimeError(
                "Authentication failed. Your auth tokens may be expired. "
                "Get fresh ones from browser DevTools and run `setup` again."
            )

        response.raise_for_status()
        data = response.json()

        if self._capture_raw:
            self.raw_responses.append(data)

        return self._parse_timeline_response(data)

    def fetch_all_bookmarks(
        self,
        count_per_page: int = 20,
        max_pages: int = 50,
        delay: float = 0,
        max_count: int | None = None,
        known_ids: set[str] | None = None,
        since_date: datetime | None = None,
    ) -> list[dict]:
        """Fetch all bookmarks with automatic pagination.

        Args:
            count_per_page: Entries to request per API call.
            max_pages: Maximum number of pages to fetch.
            delay: Seconds to sleep between pagination requests.
            max_count: Stop after collecting this many entries (None = all).
            known_ids: Stop when all entries on a page are already known.
            since_date: Stop when all entries on a page are older than this.
        """
        all_entries: list[dict] = []
        cursor: str | None = None

        for page_num in range(max_pages):
            if page_num > 0 and delay > 0:
                logger.debug("Sleeping %.1fs before next request...", delay)
                time.sleep(delay)

            logger.info("Fetching bookmarks page %d...", page_num + 1)
            page = self.fetch_bookmarks_page(
                count=count_per_page, cursor=cursor
            )

            if not page.entries:
                logger.info("No more entries. Pagination complete.")
                break

            all_entries.extend(page.entries)
            logger.info(
                "Fetched %d entries (total: %d)",
                len(page.entries),
                len(all_entries),
            )

            if max_count is not None and len(all_entries) >= max_count:
                logger.info(
                    "Reached requested count (%d). Stopping.", max_count
                )
                all_entries = all_entries[:max_count]
                break

            # Early-stop: all entries on this page are already known
            if known_ids and self._all_ids_known(page.entries, known_ids):
                logger.info(
                    "Stopping early — all %d entries on page %d are already known.",
                    len(page.entries),
                    page_num + 1,
                )
                break

            # Early-stop: all entries on this page are older than since_date
            if since_date and self._all_entries_older(page.entries, since_date):
                logger.info(
                    "Stopping early — all entries on page %d are older than %s.",
                    page_num + 1,
                    since_date.strftime("%Y-%m-%d"),
                )
                break

            cursor = page.cursor_bottom
            if not cursor:
                break

        return all_entries

    @staticmethod
    def _all_ids_known(entries: list[dict], known_ids: set[str]) -> bool:
        """Check if all tweet IDs on a page are in the known set."""
        for entry in entries:
            entry_id = entry.get("entryId", "")
            if entry_id.startswith("tweet-"):
                tweet_id = entry_id[len("tweet-"):]
                if tweet_id not in known_ids:
                    return False
        return True

    @staticmethod
    def _all_entries_older(entries: list[dict], since_date: datetime) -> bool:
        """Check if all entries on a page are older than since_date.

        Extracts created_at from the nested raw entry dict without importing
        parser logic. Returns False if any date cannot be parsed (conservative).
        """
        # Twitter date format: "Thu May 14 18:01:35 +0000 2020"
        twitter_fmt = "%a %b %d %H:%M:%S %z %Y"
        for entry in entries:
            created_at_str = (
                entry.get("content", {})
                .get("itemContent", {})
                .get("tweet_results", {})
                .get("result", {})
                .get("legacy", {})
                .get("created_at", "")
            )
            if not created_at_str:
                # Also try unwrapping TweetWithVisibilityResults
                tweet = (
                    entry.get("content", {})
                    .get("itemContent", {})
                    .get("tweet_results", {})
                    .get("result", {})
                    .get("tweet", {})
                )
                if tweet:
                    created_at_str = tweet.get("legacy", {}).get("created_at", "")
            if not created_at_str:
                return False  # Can't parse → don't stop early
            try:
                entry_date = datetime.strptime(created_at_str, twitter_fmt)
                # Make since_date timezone-aware if it isn't
                if since_date.tzinfo is None:
                    from datetime import timezone
                    since_aware = since_date.replace(tzinfo=timezone.utc)
                else:
                    since_aware = since_date
                if entry_date >= since_aware:
                    return False  # At least one entry is newer
            except ValueError:
                return False  # Can't parse → don't stop early
        return True

    def _parse_timeline_response(self, data: dict) -> BookmarksPage:
        """Extract tweet entries and cursors from GraphQL response."""
        entries: list[dict] = []
        cursor_top: str | None = None
        cursor_bottom: str | None = None

        instructions = (
            data.get("data", {})
            .get("bookmark_timeline_v2", {})
            .get("timeline", {})
            .get("instructions", [])
        )

        for instruction in instructions:
            if instruction.get("type") != "TimelineAddEntries":
                continue
            for entry in instruction.get("entries", []):
                entry_id = entry.get("entryId", "")
                if entry_id.startswith("tweet-"):
                    entries.append(entry)
                elif entry_id.startswith("cursor-top"):
                    cursor_top = entry.get("content", {}).get("value")
                elif entry_id.startswith("cursor-bottom"):
                    cursor_bottom = entry.get("content", {}).get("value")

        return BookmarksPage(
            entries=entries,
            cursor_top=cursor_top,
            cursor_bottom=cursor_bottom,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
