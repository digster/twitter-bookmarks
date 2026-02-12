"""Track processed bookmark IDs to support incremental fetches.

State is stored in .state/processed_ids.json as a JSON object:
    {
        "processed_ids": ["tweet_id_1", "tweet_id_2", ...],
        "last_fetch": "2025-01-15T14:30:00+00:00",
        "total_processed": 142
    }
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .models import Bookmark

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self, state_dir: Path = Path(".state")):
        self.state_dir = state_dir
        self.state_file = state_dir / "processed_ids.json"
        self._processed_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            self._processed_ids = set(data.get("processed_ids", []))
            logger.info(
                "Loaded %d processed bookmark IDs from state",
                len(self._processed_ids),
            )
        else:
            logger.info("No existing state found. Starting fresh.")

    def save(self) -> None:
        """Persist state to disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "processed_ids": sorted(self._processed_ids),
            "last_fetch": datetime.now(timezone.utc).isoformat(),
            "total_processed": len(self._processed_ids),
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def is_processed(self, tweet_id: str) -> bool:
        return tweet_id in self._processed_ids

    def filter_new(self, bookmarks: list[Bookmark]) -> list[Bookmark]:
        """Return only bookmarks not yet processed."""
        new = [b for b in bookmarks if not self.is_processed(b.tweet_id)]
        logger.info(
            "Found %d new bookmarks out of %d total", len(new), len(bookmarks)
        )
        return new

    def mark_all_processed(self, bookmarks: list[Bookmark]) -> None:
        """Mark a list of bookmarks as processed."""
        for b in bookmarks:
            self._processed_ids.add(b.tweet_id)

    @property
    def count(self) -> int:
        return len(self._processed_ids)

    def reset(self) -> None:
        """Clear all state (for full re-fetch)."""
        self._processed_ids.clear()
        if self.state_file.exists():
            self.state_file.unlink()
