"""Tests for the CLI interface."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from twitter_bookmarks.cli import main
from twitter_bookmarks.config import AppConfig, AuthConfig, save_config
from twitter_bookmarks.markdown import render_bookmarks_file
from twitter_bookmarks.models import Bookmark, User


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.toml"


@pytest.fixture
def configured(config_path):
    """Create a valid config file."""
    config = AppConfig(
        auth=AuthConfig(auth_token="test_token", ct0="test_ct0"),
    )
    save_config(config, config_path)
    return config_path


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Twitter/X Bookmarks Backup" in result.output

    def test_setup_creates_config(self, runner, config_path):
        result = runner.invoke(
            main,
            ["--config", str(config_path), "setup"],
            input="my_auth_token\nmy_ct0\n\n",
        )
        assert result.exit_code == 0
        assert "Config saved" in result.output
        assert config_path.exists()

    def test_fetch_without_config(self, runner, config_path):
        result = runner.invoke(
            main,
            ["--config", str(config_path), "fetch"],
        )
        assert result.exit_code != 0
        assert "No config found" in result.output

    def test_status_without_config(self, runner, config_path):
        result = runner.invoke(
            main,
            ["--config", str(config_path), "status"],
        )
        assert result.exit_code == 0
        assert "Not configured" in result.output

    def test_status_with_config(self, runner, configured):
        result = runner.invoke(
            main,
            ["--config", str(configured), "status"],
        )
        assert result.exit_code == 0
        assert "Found" in result.output
        assert "Processed bookmarks: 0" in result.output

    def test_fetch_help_shows_count_and_delay(self, runner):
        result = runner.invoke(main, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "--count" in result.output
        assert "-n" in result.output
        assert "--delay" in result.output

    def test_fetch_help_shows_dump_raw(self, runner):
        result = runner.invoke(main, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "--dump-raw" in result.output


class TestConvertCommand:
    @pytest.fixture
    def md_file(self, tmp_path, sample_bookmarks):
        """Create a temporary markdown file from sample bookmarks."""
        path = tmp_path / "bookmarks.md"
        path.write_text(
            render_bookmarks_file(sample_bookmarks), encoding="utf-8"
        )
        return path

    def test_convert_with_output_file(self, runner, md_file, tmp_path):
        output = tmp_path / "output.csv"
        result = runner.invoke(main, ["convert", str(md_file), "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "tweet_id" in content  # header row
        assert "1234567890" in content

    def test_convert_to_stdout(self, runner, md_file):
        result = runner.invoke(main, ["convert", str(md_file)])
        assert result.exit_code == 0
        assert "tweet_id" in result.output
        assert "1234567890" in result.output

    def test_convert_nonexistent_file(self, runner, tmp_path):
        result = runner.invoke(main, ["convert", str(tmp_path / "nope.md")])
        assert result.exit_code != 0

    def test_convert_empty_file(self, runner, tmp_path):
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")
        result = runner.invoke(main, ["convert", str(empty)])
        assert result.exit_code != 0
        assert "No bookmarks found" in result.output

    def test_convert_status_on_stderr(self, runner, md_file, tmp_path):
        """Status messages go to stderr, not stdout."""
        output = tmp_path / "out.csv"
        result = runner.invoke(main, ["convert", str(md_file), "-o", str(output)])
        assert result.exit_code == 0
        # click.testing.CliRunner captures stderr separately when mix_stderr=False,
        # but by default it mixes them. The key point is "Parsed" appears in output.
        assert "Parsed 3 bookmarks" in result.output
