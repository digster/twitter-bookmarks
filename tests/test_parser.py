"""Tests for the GraphQL response parser."""

from twitter_bookmarks.parser import _deep_find_user, _extract_user, parse_bookmarks


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


class TestExtractUser:
    """Tests for the resilient multi-path user extraction."""

    def test_standard_path(self):
        """Standard path: core.user_results.result.legacy"""
        tweet_result = {
            "core": {
                "user_results": {
                    "result": {
                        "rest_id": "111",
                        "legacy": {
                            "screen_name": "standarduser",
                            "name": "Standard User",
                        },
                    }
                }
            }
        }
        user = _extract_user(tweet_result, "test-1")
        assert user.username == "standarduser"
        assert user.display_name == "Standard User"
        assert user.id == "111"

    def test_singular_variant(self):
        """Singular variant: core.user_result.result.legacy"""
        tweet_result = {
            "core": {
                "user_result": {
                    "result": {
                        "rest_id": "222",
                        "legacy": {
                            "screen_name": "singularuser",
                            "name": "Singular User",
                        },
                    }
                }
            }
        }
        user = _extract_user(tweet_result, "test-2")
        assert user.username == "singularuser"
        assert user.display_name == "Singular User"
        assert user.id == "222"

    def test_flattened_path(self):
        """Flattened: core.user_results.result has screen_name directly (no legacy)."""
        tweet_result = {
            "core": {
                "user_results": {
                    "result": {
                        "rest_id": "333",
                        "screen_name": "flatuser",
                        "name": "Flat User",
                    }
                }
            }
        }
        user = _extract_user(tweet_result, "test-3")
        assert user.username == "flatuser"
        assert user.display_name == "Flat User"
        assert user.id == "333"

    def test_deep_search_fallback(self):
        """Deep search: user data buried in an unusual structure."""
        tweet_result = {
            "core": {
                "some_wrapper": {
                    "nested": {
                        "rest_id": "444",
                        "screen_name": "deepuser",
                        "name": "Deep User",
                    }
                }
            }
        }
        user = _extract_user(tweet_result, "test-4")
        assert user.username == "deepuser"
        assert user.display_name == "Deep User"

    def test_empty_core_returns_unknown(self):
        """Missing core data falls back to 'unknown'."""
        tweet_result = {"core": {}}
        user = _extract_user(tweet_result, "test-5")
        assert user.username == "unknown"
        assert user.display_name == "Unknown"

    def test_missing_core_returns_unknown(self):
        """No core key at all falls back to 'unknown'."""
        tweet_result = {}
        user = _extract_user(tweet_result, "test-6")
        assert user.username == "unknown"

    def test_singular_variant_full_entry(self):
        """Full parse of an entry using singular user_result key."""
        entries = [
            {
                "entryId": "tweet-7777777777",
                "content": {
                    "itemContent": {
                        "tweet_results": {
                            "result": {
                                "__typename": "Tweet",
                                "rest_id": "7777777777",
                                "core": {
                                    "user_result": {
                                        "result": {
                                            "rest_id": "999999",
                                            "legacy": {
                                                "screen_name": "singularuser",
                                                "name": "Singular User",
                                            },
                                        }
                                    }
                                },
                                "legacy": {
                                    "full_text": "Tweet with singular user_result key",
                                    "created_at": "Mon Feb 10 18:30:00 +0000 2025",
                                    "lang": "en",
                                    "entities": {"urls": [], "media": []},
                                },
                            }
                        }
                    }
                },
            }
        ]
        bookmarks = parse_bookmarks(entries)
        assert len(bookmarks) == 1
        assert bookmarks[0].author.username == "singularuser"
        assert bookmarks[0].tweet_url == "https://x.com/singularuser/status/7777777777"


class TestDeepFindUser:
    """Tests for the recursive user search helper."""

    def test_finds_user_at_top_level(self):
        obj = {"screen_name": "top", "name": "Top User"}
        assert _deep_find_user(obj) == obj

    def test_finds_user_nested(self):
        obj = {"a": {"b": {"screen_name": "nested", "name": "Nested"}}}
        result = _deep_find_user(obj)
        assert result["screen_name"] == "nested"

    def test_respects_max_depth(self):
        """Should not find user beyond max_depth."""
        obj = {"a": {"b": {"c": {"d": {"screen_name": "deep", "name": "Deep"}}}}}
        assert _deep_find_user(obj, max_depth=2) is None
        assert _deep_find_user(obj, max_depth=5) is not None

    def test_returns_none_for_empty(self):
        assert _deep_find_user({}) is None
        assert _deep_find_user([]) is None
        assert _deep_find_user(None) is None
