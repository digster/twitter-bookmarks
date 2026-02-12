# Twitter/X Bookmarks Backup

A simple CLI tool to back up your Twitter/X bookmarks to a markdown file.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
git clone <repo-url>
cd twitter-bookmarks
uv sync
```

### Configure

Get your Twitter/X session cookies:

1. Open [x.com](https://x.com) in your browser and log in
2. Open DevTools (`F12`) → **Application** → **Cookies** → `https://x.com`
3. Copy the values of `auth_token` and `ct0`

Run the setup wizard:

```bash
uv run twitter-bookmarks setup
```

Config is saved to `~/.config/twitter-bookmarks/config.toml` with restricted permissions.

Setup also prompts for an optional GraphQL query ID. If you skip it, the built-in default is used. To update just the query ID later (without re-entering auth tokens):

```bash
uv run twitter-bookmarks setup --query-id-only
```

You can also override the query ID via environment variable:

```bash
export TWITTER_BOOKMARKS_QUERY_ID=<new_id>
```

## Usage

### Fetch bookmarks

```bash
# Fetch and save to bookmarks.md
uv run twitter-bookmarks fetch

# Full re-fetch (ignore state, re-download all)
uv run twitter-bookmarks fetch --full

# Fetch only the 10 most recent bookmarks
uv run twitter-bookmarks fetch --count 10

# Add a delay between API requests (avoid rate limiting)
uv run twitter-bookmarks fetch --delay 3.0

# Combine: 20 latest bookmarks with 1.5s delay
uv run twitter-bookmarks fetch -n 20 --delay 1.5

# Limit pagination
uv run twitter-bookmarks fetch --max-pages 10

# Custom output file
uv run twitter-bookmarks fetch -o my-bookmarks.md

# Verbose logging
uv run twitter-bookmarks -v fetch
```

### Check status

```bash
uv run twitter-bookmarks status
```

## Output

Bookmarks are saved to a single `bookmarks.md` file, grouped by date (newest first):

```markdown
# Twitter/X Bookmarks

*Last updated: 2025-02-11 14:30 | 142 bookmarks*

## February 10, 2025

### @simonw
*Simon Willison*

> Tweet text with expanded URLs...

- **Tweet:** [link](https://x.com/simonw/status/123)
- **Date:** 2025-02-10 18:30 UTC
- **Links:** [example.com/...](https://example.com/article)

---
```

## Viewer

A standalone HTML viewer for browsing exported bookmarks visually. No server or build step needed.

### Usage

1. Open `viewer.html` in any browser
2. Drag-and-drop your exported `.md` file onto the drop zone (or use the file picker)
3. Browse your bookmarks with search, sort, and media previews

### Features

- **List/grid view toggle** — compact list mode (default) for high-density scanning; grid mode for rich card layout with full media
- List mode: click any row to expand and reveal full text, media, and links
- Full-text search across usernames, display names, and tweet text
- Sort by newest or oldest first
- Dark/light theme toggle (persists across sessions)
- View mode persists across sessions
- Photo grids (1-4 images), video/GIF thumbnails with play overlay
- Reply and quote tweet badges
- External link display with domain names
- Numbered pagination with prev/next controls (replaces infinite scroll)
- Configurable page size (20, 50, or 100 per page) — persisted across sessions
- URL hash persistence (`#page=N`) — bookmarkable page positions
- Responsive layout (3-col → 2-col → 1-col in grid mode)
- Keyboard shortcuts: `/` to focus search, `Escape` to clear, `←`/`→` arrow keys to navigate pages
- Stats bar with total count, date range, filtered count, and current page

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest -v

# Run with debug logging
uv run twitter-bookmarks -v fetch
```

## How it works

The tool calls Twitter's internal GraphQL API directly using cookie-based authentication (same approach as the Twitter web client). No API keys or developer account needed.

**Auth tokens expire periodically.** If you get authentication errors, get fresh `auth_token` and `ct0` values from your browser and run `setup` again.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Authentication failed` | Tokens expired. Re-run `setup` with fresh cookies. |
| `Rate limited` | Wait for the indicated time and retry. |
| `GraphQL query ID is stale (404)` | Twitter rotated the query ID. Open `x.com/i/bookmarks` in your browser, open DevTools -> Network, filter for "Bookmarks", and copy the ID from the URL (between `/graphql/` and `/Bookmarks`). Then run `setup --query-id-only` or set `TWITTER_BOOKMARKS_QUERY_ID` env var. |
| Empty results | May also be a stale query ID. Try the 404 fix above. |
