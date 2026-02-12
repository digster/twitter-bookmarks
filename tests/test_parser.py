"""Tests for the GraphQL response parser."""

from twitter_bookmarks.parser import parse_bookmarks


class TestParseBookmarks:
    def test_parses_correct_number_of_entries(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        assert len(bookmarks) == 3

    def test_parses_basic_tweet(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        b = bookmarks[0]  # tweet-1234567890
        assert b.tweet_id == "1234567890"
        assert b.author.username == "testuser"
        assert b.author.display_name == "Test User"
        assert b.tweet_url == "https://x.com/testuser/status/1234567890"
        assert b.lang == "en"

    def test_expands_tco_urls(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        b = bookmarks[0]
        # t.co link should be replaced with expanded URL
        assert "https://example.com/article" in b.text
        assert "https://t.co/abc123" not in b.text
        assert "https://example.com/article" in b.urls

    def test_parses_media(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        b = bookmarks[1]  # tweet with photo
        assert len(b.media) == 1
        assert b.media[0].type == "photo"
        assert b.media[0].url == "https://pbs.twimg.com/media/test123.jpg"

    def test_strips_media_tco_from_text(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        b = bookmarks[1]
        # t.co media URL should be stripped from text
        assert "https://t.co/img456" not in b.text

    def test_parses_quote_tweet(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        b = bookmarks[2]  # quote tweet
        assert b.is_quote is True
        assert (
            b.quoted_tweet_url
            == "https://x.com/originalauthor/status/4444444444"
        )

    def test_parses_created_at(self, raw_entries):
        bookmarks = parse_bookmarks(raw_entries)
        b = bookmarks[0]
        assert b.created_at.year == 2025
        assert b.created_at.month == 2
        assert b.created_at.day == 10

    def test_skips_malformed_entries(self):
        """Malformed entries are skipped, not raised."""
        entries = [
            {
                "entryId": "tweet-bad",
                "content": {"itemContent": {"tweet_results": {}}},
            }
        ]
        bookmarks = parse_bookmarks(entries)
        assert len(bookmarks) == 0

    def test_handles_tombstone_tweets(self):
        """Deleted/tombstone tweets return None."""
        entries = [
            {
                "entryId": "tweet-deleted",
                "content": {
                    "itemContent": {
                        "tweet_results": {
                            "result": {"__typename": "TweetTombstone"}
                        }
                    }
                },
            }
        ]
        bookmarks = parse_bookmarks(entries)
        assert len(bookmarks) == 0

    def test_handles_visibility_wrapper(self):
        """TweetWithVisibilityResults wrapper is unwrapped."""
        entries = [
            {
                "entryId": "tweet-wrapped",
                "content": {
                    "itemContent": {
                        "tweet_results": {
                            "result": {
                                "__typename": "TweetWithVisibilityResults",
                                "tweet": {
                                    "rest_id": "wrapped123",
                                    "core": {
                                        "user_results": {
                                            "result": {
                                                "rest_id": "u1",
                                                "legacy": {
                                                    "screen_name": "wrappeduser",
                                                    "name": "Wrapped",
                                                },
                                            }
                                        }
                                    },
                                    "legacy": {
                                        "full_text": "Wrapped tweet",
                                        "created_at": "Mon Feb 10 18:30:00 +0000 2025",
                                        "lang": "en",
                                        "entities": {"urls": [], "media": []},
                                    },
                                },
                            }
                        }
                    }
                },
            }
        ]
        bookmarks = parse_bookmarks(entries)
        assert len(bookmarks) == 1
        assert bookmarks[0].tweet_id == "wrapped123"
