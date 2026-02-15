"""Tests for the CSV converter."""

import csv
import io
from datetime import datetime, timezone

from twitter_bookmarks.converter import CSV_COLUMNS, bookmarks_to_csv
from twitter_bookmarks.models import Bookmark, MediaItem, User


class TestBookmarksToCsv:
    def test_header_row(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == CSV_COLUMNS

    def test_row_count(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        # Header + 3 data rows
        assert len(rows) == 4

    def test_basic_fields(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)

        first = rows[0]
        assert first["tweet_id"] == "1234567890"
        assert first["username"] == "testuser"
        assert first["display_name"] == "Test User"
        assert first["tweet_url"] == "https://x.com/testuser/status/1234567890"
        assert "test tweet" in first["text"]

    def test_date_iso_format(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.DictReader(io.StringIO(result))
        first = next(reader)
        assert first["date"] == "2025-02-10T18:30:00+00:00"

    def test_pipe_separated_links(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.DictReader(io.StringIO(result))
        first = next(reader)
        assert first["links"] == "https://example.com/article"

    def test_pipe_separated_media(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        photo_row = rows[1]  # photouser
        assert photo_row["media_urls"] == "https://pbs.twimg.com/media/test123.jpg"
        assert photo_row["media_types"] == "photo"

    def test_multiple_media(self):
        bookmark = Bookmark(
            tweet_id="999",
            author=User(id="1", username="multi", display_name="Multi Media"),
            text="Multiple media",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            tweet_url="https://x.com/multi/status/999",
            media=[
                MediaItem(type="photo", url="https://img1.jpg", expanded_url=""),
                MediaItem(type="video", url="https://vid1.mp4", expanded_url=""),
            ],
        )
        result = bookmarks_to_csv([bookmark])
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        assert row["media_urls"] == "https://img1.jpg|https://vid1.mp4"
        assert row["media_types"] == "photo|video"

    def test_boolean_fields(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)

        # First bookmark: not a reply, not a quote
        assert rows[0]["is_reply"] == "false"
        assert rows[0]["is_quote"] == "false"

        # Third bookmark: is a quote
        assert rows[2]["is_quote"] == "true"
        assert rows[2]["quoted_tweet_url"] == "https://x.com/originalauthor/status/4444444444"

    def test_none_fields_as_empty(self, sample_bookmarks):
        result = bookmarks_to_csv(sample_bookmarks)
        reader = csv.DictReader(io.StringIO(result))
        first = next(reader)
        assert first["reply_to_user"] == ""
        assert first["quoted_tweet_url"] == ""

    def test_newlines_in_text(self):
        bookmark = Bookmark(
            tweet_id="888",
            author=User(id="1", username="newliner", display_name="New Liner"),
            text="Line one\nLine two\nLine three",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            tweet_url="https://x.com/newliner/status/888",
        )
        result = bookmarks_to_csv([bookmark])
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        assert row["text"] == "Line one\nLine two\nLine three"

    def test_commas_in_text(self):
        bookmark = Bookmark(
            tweet_id="777",
            author=User(id="1", username="commaman", display_name="Comma, Man"),
            text="Hello, world, this has, commas",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            tweet_url="https://x.com/commaman/status/777",
        )
        result = bookmarks_to_csv([bookmark])
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        assert row["text"] == "Hello, world, this has, commas"
        assert row["display_name"] == "Comma, Man"

    def test_output_to_file(self, tmp_path, sample_bookmarks):
        output_file = tmp_path / "output.csv"
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            bookmarks_to_csv(sample_bookmarks, f)

        file_content = output_file.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(file_content))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["tweet_id"] == "1234567890"

    def test_output_to_stringio(self, sample_bookmarks):
        buf = io.StringIO()
        result = bookmarks_to_csv(sample_bookmarks, buf)
        assert buf.getvalue() == result

    def test_empty_bookmarks(self):
        result = bookmarks_to_csv([])
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        # Only header row
        assert len(rows) == 1
        assert rows[0] == CSV_COLUMNS

    def test_reply_fields(self):
        bookmark = Bookmark(
            tweet_id="666",
            author=User(id="1", username="replier", display_name="Replier"),
            text="This is a reply",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            tweet_url="https://x.com/replier/status/666",
            is_reply=True,
            reply_to_user="originaluser",
        )
        result = bookmarks_to_csv([bookmark])
        reader = csv.DictReader(io.StringIO(result))
        row = next(reader)
        assert row["is_reply"] == "true"
        assert row["reply_to_user"] == "originaluser"
