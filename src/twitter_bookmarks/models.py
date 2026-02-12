"""Data models for parsed bookmark/tweet data."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    id: str
    username: str  # screen_name (handle without @)
    display_name: str  # display name


@dataclass
class MediaItem:
    type: str  # "photo", "video", "animated_gif"
    url: str  # direct media URL
    expanded_url: str  # t.co expanded URL


@dataclass
class Bookmark:
    tweet_id: str
    author: User
    text: str  # full_text with t.co URLs replaced by expanded versions
    created_at: datetime
    tweet_url: str  # https://x.com/{username}/status/{tweet_id}
    urls: list[str] = field(default_factory=list)
    media: list[MediaItem] = field(default_factory=list)
    is_reply: bool = False
    reply_to_user: str | None = None
    is_quote: bool = False
    quoted_tweet_url: str | None = None
    lang: str = "en"
