"""Shared test fixtures."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from twitter_bookmarks.models import Bookmark, MediaItem, User

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def bookmarks_response() -> dict:
    """Load the sample GraphQL bookmarks response."""
    with open(FIXTURES_DIR / "bookmarks_response.json") as f:
        return json.load(f)


@pytest.fixture
def raw_entries(bookmarks_response) -> list[dict]:
    """Extract raw tweet entries from the fixture (excluding cursors)."""
    entries = []
    for instruction in (
        bookmarks_response["data"]["bookmark_timeline_v2"]["timeline"][
            "instructions"
        ]
    ):
        if instruction.get("type") == "TimelineAddEntries":
            for entry in instruction["entries"]:
                if entry["entryId"].startswith("tweet-"):
                    entries.append(entry)
    return entries


@pytest.fixture
def sample_bookmarks() -> list[Bookmark]:
    """A list of sample Bookmark objects for testing."""
    return [
        Bookmark(
            tweet_id="1234567890",
            author=User(id="111", username="testuser", display_name="Test User"),
            text="This is a test tweet with a link https://example.com/article",
            created_at=datetime(2025, 2, 10, 18, 30, 0, tzinfo=timezone.utc),
            tweet_url="https://x.com/testuser/status/1234567890",
            urls=["https://example.com/article"],
        ),
        Bookmark(
            tweet_id="9876543210",
            author=User(
                id="222", username="photouser", display_name="Photo User"
            ),
            text="Check out this image",
            created_at=datetime(2025, 2, 9, 12, 0, 0, tzinfo=timezone.utc),
            tweet_url="https://x.com/photouser/status/9876543210",
            media=[
                MediaItem(
                    type="photo",
                    url="https://pbs.twimg.com/media/test123.jpg",
                    expanded_url="https://x.com/photouser/status/9876543210/photo/1",
                )
            ],
        ),
        Bookmark(
            tweet_id="5555555555",
            author=User(
                id="333", username="quoter", display_name="The Quoter"
            ),
            text="Great take on this topic",
            created_at=datetime(2025, 2, 8, 9, 0, 0, tzinfo=timezone.utc),
            tweet_url="https://x.com/quoter/status/5555555555",
            is_quote=True,
            quoted_tweet_url="https://x.com/originalauthor/status/4444444444",
        ),
    ]
