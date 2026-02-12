"""Tests for the state manager."""

import json

import pytest

from twitter_bookmarks.state import StateManager


@pytest.fixture
def state_dir(tmp_path):
    return tmp_path / ".state"


@pytest.fixture
def state(state_dir):
    return StateManager(state_dir)


class TestStateManager:
    def test_starts_empty(self, state):
        assert state.count == 0

    def test_save_and_reload(self, state, state_dir, sample_bookmarks):
        state.mark_all_processed(sample_bookmarks)
        state.save()

        # Reload from disk
        reloaded = StateManager(state_dir)
        assert reloaded.count == 3
        assert reloaded.is_processed("1234567890")
        assert reloaded.is_processed("9876543210")
        assert reloaded.is_processed("5555555555")

    def test_filter_new(self, state, sample_bookmarks):
        # Mark first two as processed
        state.mark_all_processed(sample_bookmarks[:2])
        new = state.filter_new(sample_bookmarks)
        assert len(new) == 1
        assert new[0].tweet_id == "5555555555"

    def test_filter_new_all_new(self, state, sample_bookmarks):
        new = state.filter_new(sample_bookmarks)
        assert len(new) == 3

    def test_filter_new_none_new(self, state, sample_bookmarks):
        state.mark_all_processed(sample_bookmarks)
        new = state.filter_new(sample_bookmarks)
        assert len(new) == 0

    def test_reset(self, state, state_dir, sample_bookmarks):
        state.mark_all_processed(sample_bookmarks)
        state.save()
        assert state.count == 3

        state.reset()
        assert state.count == 0
        assert not (state_dir / "processed_ids.json").exists()

    def test_state_file_format(self, state, state_dir, sample_bookmarks):
        state.mark_all_processed(sample_bookmarks)
        state.save()

        data = json.loads((state_dir / "processed_ids.json").read_text())
        assert "processed_ids" in data
        assert "last_fetch" in data
        assert "total_processed" in data
        assert data["total_processed"] == 3
