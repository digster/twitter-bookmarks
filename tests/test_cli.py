"""Tests for the CLI interface."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from twitter_bookmarks.cli import main
from twitter_bookmarks.config import AppConfig, AuthConfig, save_config


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
