"""Configuration loading and saving.

Config file location: ~/.config/twitter-bookmarks/config.toml

Schema:
    [auth]
    auth_token = "..."
    ct0 = "..."

    [output]
    bookmarks_file = "bookmarks.md"

    [state]
    state_dir = ".state"

    [fetch]
    delay = 2.0

    [api]
    query_id = "..."  # GraphQL query ID for Bookmarks endpoint
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".config" / "twitter-bookmarks"
CONFIG_FILE = CONFIG_DIR / "config.toml"


@dataclass
class AuthConfig:
    auth_token: str
    ct0: str


@dataclass
class AppConfig:
    auth: AuthConfig
    bookmarks_file: Path = Path("bookmarks.md")
    state_dir: Path = Path(".state")
    fetch_delay: float = 2.0
    query_id: str | None = None


def load_config(config_path: Path = CONFIG_FILE) -> AppConfig:
    """Load and validate config from TOML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    auth_data = data.get("auth", {})
    auth_token = auth_data.get("auth_token", "")
    ct0 = auth_data.get("ct0", "")

    if not auth_token or not ct0:
        raise ValueError("Config missing required auth.auth_token and auth.ct0")

    output_data = data.get("output", {})
    state_data = data.get("state", {})
    fetch_data = data.get("fetch", {})
    api_data = data.get("api", {})

    return AppConfig(
        auth=AuthConfig(auth_token=auth_token, ct0=ct0),
        bookmarks_file=Path(output_data.get("bookmarks_file", "bookmarks.md")),
        state_dir=Path(state_data.get("state_dir", ".state")),
        fetch_delay=float(fetch_data.get("delay", 2.0)),
        query_id=api_data.get("query_id"),
    )


def save_config(config: AppConfig, config_path: Path = CONFIG_FILE) -> None:
    """Write config to TOML file with restricted permissions."""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "auth": {
            "auth_token": config.auth.auth_token,
            "ct0": config.auth.ct0,
        },
        "output": {
            "bookmarks_file": str(config.bookmarks_file),
        },
        "state": {
            "state_dir": str(config.state_dir),
        },
        "fetch": {
            "delay": config.fetch_delay,
        },
    }

    if config.query_id:
        data["api"] = {"query_id": config.query_id}

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    # Restrict permissions — file contains auth secrets
    os.chmod(config_path, 0o600)


def config_exists(config_path: Path = CONFIG_FILE) -> bool:
    """Check if config file exists."""
    return config_path.exists()
