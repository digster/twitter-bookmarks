"""Tests for the Twitter API client."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from twitter_bookmarks.client import BOOKMARKS_QUERY_ID, TwitterClient

GRAPHQL_URL = f"https://x.com/i/api/graphql/{BOOKMARKS_QUERY_ID}/Bookmarks"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_response() -> dict:
    with open(FIXTURES_DIR / "bookmarks_response.json") as f:
        return json.load(f)


@pytest.fixture
def empty_response() -> dict:
    return {
        "data": {
            "bookmark_timeline_v2": {
                "timeline": {
                    "instructions": [
                        {"type": "TimelineAddEntries", "entries": []}
                    ]
                }
            }
        }
    }


class TestTwitterClient:
    @respx.mock
    def test_fetch_single_page(self, fixture_response):
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json=fixture_response)
        )

        with TwitterClient("fake_auth", "fake_ct0") as client:
            page = client.fetch_bookmarks_page()

        assert len(page.entries) == 3
        assert page.cursor_top == "cursor_top_value_abc"
        assert page.cursor_bottom == "cursor_bottom_value_xyz"

    @respx.mock
    def test_fetch_all_stops_on_empty(self, fixture_response, empty_response):
        route = respx.get(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(200, json=fixture_response),
            httpx.Response(200, json=empty_response),
        ]

        with TwitterClient("fake_auth", "fake_ct0") as client:
            entries = client.fetch_all_bookmarks(max_pages=5)

        assert len(entries) == 3  # only from first page

    @respx.mock
    def test_auth_failure_raises(self):
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(401, json={"errors": [{"message": "Unauthorized"}]})
        )

        with TwitterClient("bad_auth", "bad_ct0") as client:
            with pytest.raises(RuntimeError, match="Authentication failed"):
                client.fetch_bookmarks_page()

    @respx.mock
    def test_rate_limit_raises(self):
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(
                429,
                json={"errors": [{"message": "Rate limit"}]},
                headers={"x-rate-limit-reset": "9999999999"},
            )
        )

        with TwitterClient("auth", "ct0") as client:
            with pytest.raises(RuntimeError, match="Rate limited"):
                client.fetch_bookmarks_page()

    @respx.mock
    def test_max_pages_respected(self, fixture_response):
        # Always return data (never empty) to test max_pages cutoff
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json=fixture_response)
        )

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(max_pages=2)

        # 3 entries per page * 2 pages
        assert len(entries) == 6

    @respx.mock
    @patch("twitter_bookmarks.client.time.sleep")
    def test_delay_between_pages(self, mock_sleep, fixture_response):
        """Verify delay is called between pages but not before the first."""
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json=fixture_response)
        )

        with TwitterClient("auth", "ct0") as client:
            client.fetch_all_bookmarks(max_pages=3, delay=1.5)

        # 3 pages fetched, delay called before page 2 and 3 (not page 1)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.5)

    @respx.mock
    def test_max_count_stops_early(self, fixture_response):
        """Verify pagination stops once max_count entries are collected."""
        route = respx.get(GRAPHQL_URL)
        route.mock(return_value=httpx.Response(200, json=fixture_response))

        with TwitterClient("auth", "ct0") as client:
            # fixture returns 3 per page; max_count=3 should stop after page 1
            entries = client.fetch_all_bookmarks(
                max_pages=10, max_count=3
            )

        assert len(entries) == 3
        assert route.call_count == 1  # only one page fetched

    @respx.mock
    def test_max_count_truncates(self, fixture_response):
        """Verify result is truncated to exactly max_count."""
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json=fixture_response)
        )

        with TwitterClient("auth", "ct0") as client:
            # fixture returns 3 per page; max_count=2 should truncate
            entries = client.fetch_all_bookmarks(
                max_pages=10, max_count=2
            )

        assert len(entries) == 2

    @respx.mock
    def test_stale_query_id_raises(self):
        """Verify 404 gives a helpful error about stale query ID."""
        respx.get(GRAPHQL_URL).mock(
            return_value=httpx.Response(404, json={"errors": [{"message": "Not Found"}]})
        )

        with TwitterClient("auth", "ct0") as client:
            with pytest.raises(RuntimeError, match="query ID is stale"):
                client.fetch_bookmarks_page()

    @respx.mock
    def test_custom_query_id(self, fixture_response):
        """Verify custom query_id builds a different URL."""
        custom_url = "https://x.com/i/api/graphql/CustomQueryId123/Bookmarks"
        respx.get(custom_url).mock(
            return_value=httpx.Response(200, json=fixture_response)
        )

        with TwitterClient("auth", "ct0", query_id="CustomQueryId123") as client:
            page = client.fetch_bookmarks_page()

        assert len(page.entries) == 3

    @respx.mock
    def test_known_ids_stops_when_all_known(self, fixture_response):
        """Stop pagination when all entries on a page are already known."""
        route = respx.get(GRAPHQL_URL)
        route.mock(return_value=httpx.Response(200, json=fixture_response))

        known = {"1234567890", "9876543210", "5555555555"}

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(
                max_pages=10, known_ids=known
            )

        # Fetches page 1, sees all IDs known, stops
        assert route.call_count == 1
        assert len(entries) == 3

    @respx.mock
    def test_known_ids_continues_when_partial(self, fixture_response, empty_response):
        """Continue pagination when some entries are new."""
        route = respx.get(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(200, json=fixture_response),
            httpx.Response(200, json=empty_response),
        ]

        # Only one of three is known → should continue
        known = {"1234567890"}

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(
                max_pages=10, known_ids=known
            )

        assert route.call_count == 2
        assert len(entries) == 3

    @respx.mock
    def test_since_date_stops_when_all_older(self, fixture_response):
        """Stop when all entries on a page are older than since_date."""
        route = respx.get(GRAPHQL_URL)
        route.mock(return_value=httpx.Response(200, json=fixture_response))

        # All fixture entries are from Feb 8-10 2025
        # Set since_date to after all of them
        since = datetime(2025, 2, 11, 0, 0, 0, tzinfo=timezone.utc)

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(
                max_pages=10, since_date=since
            )

        assert route.call_count == 1
        assert len(entries) == 3

    @respx.mock
    def test_since_date_continues_when_some_newer(self, fixture_response, empty_response):
        """Continue when some entries are newer than since_date."""
        route = respx.get(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(200, json=fixture_response),
            httpx.Response(200, json=empty_response),
        ]

        # Feb 9 is between oldest (Feb 8) and newest (Feb 10)
        since = datetime(2025, 2, 9, 0, 0, 0, tzinfo=timezone.utc)

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(
                max_pages=10, since_date=since
            )

        assert route.call_count == 2

    @respx.mock
    def test_no_early_stop_params_unchanged(self, fixture_response, empty_response):
        """Without early-stop params, behavior is identical to before."""
        route = respx.get(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(200, json=fixture_response),
            httpx.Response(200, json=empty_response),
        ]

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(max_pages=10)

        assert route.call_count == 2
        assert len(entries) == 3

    @respx.mock
    def test_max_count_beats_early_stop(self, fixture_response):
        """max_count triggers before early-stop gets a chance to check."""
        route = respx.get(GRAPHQL_URL)
        route.mock(return_value=httpx.Response(200, json=fixture_response))

        known = {"1234567890", "9876543210", "5555555555"}

        with TwitterClient("auth", "ct0") as client:
            entries = client.fetch_all_bookmarks(
                max_pages=10, max_count=2, known_ids=known
            )

        # max_count=2 truncates and stops before known_ids check
        assert len(entries) == 2
        assert route.call_count == 1
