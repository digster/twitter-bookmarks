"""Tests for the markdown renderer."""

from datetime import datetime, timezone

from twitter_bookmarks.markdown import (
    extract_ids_from_markdown,
    extract_latest_date,
    render_bookmarks_file,
    strip_legacy_headers,
)
from twitter_bookmarks.models import Bookmark, User


class TestRenderBookmarksFile:
    def test_no_header_present(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert not md.startswith("# Twitter/X Bookmarks")
        assert "*Last updated" not in md

    def test_renders_empty_bookmarks(self):
        md = render_bookmarks_file([])
        assert md == ""

    def test_no_date_group_headers(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "## February 10, 2025" not in md
        assert "## February 09, 2025" not in md
        assert "## February 08, 2025" not in md

    def test_newest_first(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        lines = md.split("\n")
        date_lines = [l for l in lines if l.startswith("- **Date:**")]
        assert len(date_lines) == 3
        # First date line should be newest (Feb 10)
        assert "2025-02-10" in date_lines[0]
        assert "2025-02-09" in date_lines[1]
        assert "2025-02-08" in date_lines[2]

    def test_renders_author(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "### @testuser" in md
        assert "*Test User*" in md

    def test_renders_text_as_blockquote(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "> This is a test tweet" in md

    def test_renders_tweet_link(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "https://x.com/testuser/status/1234567890" in md

    def test_renders_urls(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "**Links:**" in md
        assert "https://example.com/article" in md

    def test_renders_media(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "**Media:**" in md
        assert "[photo]" in md

    def test_renders_quote_info(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "**Quote of:**" in md
        assert "https://x.com/originalauthor/status/4444444444" in md

    def test_separators_between_entries(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert md.count("---") == 3

    def test_render_includes_tweet_id(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "- **ID:** 1234567890" in md
        assert "- **ID:** 9876543210" in md
        assert "- **ID:** 5555555555" in md


class TestStripLegacyHeaders:
    def test_strips_main_header(self):
        content = "# Twitter/X Bookmarks\n\n### @user\n"
        result = strip_legacy_headers(content)
        assert "# Twitter/X Bookmarks" not in result
        assert "### @user" in result

    def test_strips_last_updated(self):
        content = "*Last updated: 2025-02-14 12:00 | 100 bookmarks*\n\n### @user\n"
        result = strip_legacy_headers(content)
        assert "*Last updated" not in result
        assert "### @user" in result

    def test_strips_date_group_headers(self):
        content = "## February 10, 2025\n\n### @user\ntext\n---\n## February 09, 2025\n\n### @other\n"
        result = strip_legacy_headers(content)
        assert "## February 10, 2025" not in result
        assert "## February 09, 2025" not in result
        assert "### @user" in result
        assert "### @other" in result

    def test_strips_no_bookmarks_found(self):
        content = "# Twitter/X Bookmarks\n\n*No bookmarks found.*\n"
        result = strip_legacy_headers(content)
        assert result.strip() == ""

    def test_preserves_non_header_content(self):
        content = "### @user\n*Display Name*\n\n> Tweet text\n\n- **Tweet:** [url](url)\n- **Date:** 2025-02-10 18:30 UTC\n- **ID:** 123\n\n---\n"
        result = strip_legacy_headers(content)
        assert result == content

    def test_removes_leading_blank_lines(self):
        content = "\n\n\n### @user\n"
        result = strip_legacy_headers(content)
        assert result.startswith("### @user")

    def test_strips_all_legacy_combined(self):
        content = (
            "# Twitter/X Bookmarks\n\n"
            "*Last updated: 2025-02-14 12:00 | 100 bookmarks*\n\n"
            "## February 10, 2025\n\n"
            "### @user\n*Name*\n\n> Text\n\n"
            "- **Tweet:** [url](url)\n"
            "- **Date:** 2025-02-10 18:30 UTC\n"
            "- **ID:** 123\n\n---\n"
        )
        result = strip_legacy_headers(content)
        assert "# Twitter/X Bookmarks" not in result
        assert "*Last updated" not in result
        assert "## February 10, 2025" not in result
        assert "### @user" in result
        assert "- **ID:** 123" in result


class TestExtractIdsFromMarkdown:
    def test_extracts_from_id_lines(self):
        content = (
            "### @user\n- **ID:** 111\n---\n"
            "### @other\n- **ID:** 222\n---\n"
        )
        ids = extract_ids_from_markdown(content)
        assert ids == {"111", "222"}

    def test_falls_back_to_tweet_urls(self):
        content = (
            "### @user\n"
            "- **Tweet:** [https://x.com/user/status/111](https://x.com/user/status/111)\n"
            "---\n"
            "### @other\n"
            "- **Tweet:** [https://x.com/other/status/222](https://x.com/other/status/222)\n"
            "---\n"
        )
        ids = extract_ids_from_markdown(content)
        assert ids == {"111", "222"}

    def test_prefers_id_lines_over_urls(self):
        content = (
            "### @user\n"
            "- **Tweet:** [https://x.com/user/status/111](https://x.com/user/status/111)\n"
            "- **ID:** 111\n"
            "---\n"
        )
        ids = extract_ids_from_markdown(content)
        assert ids == {"111"}

    def test_empty_content(self):
        assert extract_ids_from_markdown("") == set()

    def test_no_matches(self):
        assert extract_ids_from_markdown("just some text\n") == set()

    def test_extracts_from_rendered_bookmarks(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        ids = extract_ids_from_markdown(md)
        assert ids == {"1234567890", "9876543210", "5555555555"}


class TestExtractLatestDate:
    def test_extracts_first_date(self):
        content = (
            "- **Date:** 2025-02-10 18:30 UTC\n"
            "---\n"
            "- **Date:** 2025-02-09 12:00 UTC\n"
        )
        result = extract_latest_date(content)
        assert result == datetime(2025, 2, 10, 18, 30, tzinfo=timezone.utc)

    def test_returns_none_for_empty(self):
        assert extract_latest_date("") is None

    def test_returns_none_for_no_dates(self):
        assert extract_latest_date("just some text\n") is None

    def test_works_with_rendered_bookmarks(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        result = extract_latest_date(md)
        # sample_bookmarks[0] is Feb 10, 18:30 UTC (newest)
        assert result == datetime(2025, 2, 10, 18, 30, tzinfo=timezone.utc)
