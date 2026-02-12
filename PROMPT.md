# Prompts

## 2025-02-11
- Build an app similar to https://github.com/alexknowshtml/smaug. Main purpose is to backup bookmarks in markdown. Keep it simple and initially only build the functionality to backup the bookmarks in markdown.

## 2026-02-11
- Add configurable delay between API pagination requests (default 2s, via config and --delay flag) and a --count/-n flag to fetch only the N most recent bookmarks.
- Fix "Unknown" author usernames: add resilient multi-path user extraction (`_extract_user()` with 4 fallback paths), `--dump-raw` diagnostic flag, and debug logging for key visibility.
