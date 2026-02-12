# Architecture

## Overview

A Python CLI tool that backs up Twitter/X bookmarks to a single markdown file. Uses Twitter's internal GraphQL API with cookie-based authentication.

## Data Flow

```
Twitter GraphQL API ──→ client.py ──→ parser.py ──→ markdown.py ──→ bookmarks.md
      (httpx)         (raw JSON)    (Bookmark    (markdown
                                     objects)     string)
                                        │
                                        ▼
                                    state.py
                                 (.state/processed_ids.json)
```

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Click CLI commands (setup, fetch, status). Orchestrates all modules. |
| `config.py` | TOML config at `~/.config/twitter-bookmarks/config.toml`. Stores auth tokens and optional `query_id` under `[api]`. |
| `client.py` | Twitter GraphQL API client. Cookie auth, pagination, error handling (including 404 stale query ID detection). Accepts per-instance `query_id`. |
| `parser.py` | Parses deeply nested GraphQL JSON into `Bookmark` dataclasses. |
| `models.py` | Dataclasses: `Bookmark`, `User`, `MediaItem`. |
| `markdown.py` | Renders bookmark list to a single markdown file grouped by date. |
| `state.py` | Tracks processed tweet IDs in `.state/processed_ids.json` for incremental fetches. |
| `logging_config.py` | Logging setup with configurable verbosity. |

## Authentication

Twitter's internal API uses cookie-based auth with three components:
- **Bearer token** — Static, public token shared by all web clients (hardcoded)
- **auth_token cookie** — User session token (from browser DevTools)
- **ct0 cookie** — CSRF token, also sent as `x-csrf-token` header

## API Details

- **Endpoint:** `GET /i/api/graphql/{queryId}/Bookmarks`
- **Query ID:** Rotates every few weeks. Resolution order: `AppConfig.query_id` (from config `[api]` section or `setup`) > `TWITTER_BOOKMARKS_QUERY_ID` env var > hardcoded default. A 404 response triggers a descriptive error with instructions to update the ID.
- **Pagination:** Cursor-based. Each response includes `cursor-bottom` for the next page.
- **Feature flags:** Boolean flags sent with each request. Hardcoded to match current web client.

## Key Directories

```
src/twitter_bookmarks/    # Source code
tests/                    # Tests with JSON fixtures in tests/fixtures/
.state/                   # Runtime state (gitignored)
~/.config/twitter-bookmarks/  # Config with auth tokens (restricted permissions)
```
