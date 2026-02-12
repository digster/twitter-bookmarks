"""Tests for the markdown renderer."""

from twitter_bookmarks.markdown import render_bookmarks_file


class TestRenderBookmarksFile:
    def test_renders_header(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert md.startswith("# Twitter/X Bookmarks")
        assert "3 bookmarks" in md

    def test_renders_empty_bookmarks(self):
        md = render_bookmarks_file([])
        assert "No bookmarks found" in md

    def test_groups_by_date(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        assert "## February 10, 2025" in md
        assert "## February 09, 2025" in md
        assert "## February 08, 2025" in md

    def test_newest_first(self, sample_bookmarks):
        md = render_bookmarks_file(sample_bookmarks)
        idx_feb10 = md.index("February 10")
        idx_feb09 = md.index("February 09")
        idx_feb08 = md.index("February 08")
        assert idx_feb10 < idx_feb09 < idx_feb08

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
        assert md.count("---") == 3  # one separator per bookmark
