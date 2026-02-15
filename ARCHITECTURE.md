# Architecture

## Overview

A Python CLI tool that backs up Twitter/X bookmarks to a single markdown file. Uses Twitter's internal GraphQL API with cookie-based authentication.

## Data Flow

**`bookmarks.md` is the source of truth.** No JSON state files are needed for correctness — known IDs and latest date are extracted directly from the markdown.

### Full Fetch (`--full`)

```
Twitter GraphQL API ──→ client.py ──→ parser.py ──→ markdown.py ──→ bookmarks.md
      (httpx)         (raw JSON)    (Bookmark       (render all,
                                     objects)        overwrite)
```

### Incremental Fetch (default)

```
Read bookmarks.md ──→ extract_ids + extract_latest_date ──→ Fetch with early-stop
                          (markdown.py helpers)                (known_ids + since_date)
                                                                        │
                                                                        ▼
                       Prepend to bookmarks.md ←── Render new only ←── Dedup + Parse
                       (strip legacy headers)       (markdown.py)      (filter by known_ids)
```

Early-stop triggers per-page: if **all** entries on a page are known IDs or older than the cutoff date, pagination stops. Both checks are conservative — unparseable data causes continuation rather than premature stopping.

`processed_ids.json` is still maintained for the `status` command's count display, but the fetch command does not depend on it.

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Click CLI commands (setup, fetch, status). Orchestrates all modules. |
| `config.py` | TOML config at `~/.config/twitter-bookmarks/config.toml`. Stores auth tokens and optional `query_id` under `[api]`. |
| `client.py` | Twitter GraphQL API client. Cookie auth, pagination with early-stop support (known IDs + date cutoff), error handling (including 404 stale query ID detection). Accepts per-instance `query_id`. |
| `parser.py` | Parses deeply nested GraphQL JSON into `Bookmark` dataclasses. |
| `models.py` | Dataclasses: `Bookmark`, `User`, `MediaItem`. |
| `markdown.py` | Renders bookmark list to markdown. Also provides `extract_ids_from_markdown()`, `extract_latest_date()`, and `strip_legacy_headers()` for deriving state from the markdown file. |
| `state.py` | Tracks processed tweet IDs (`.state/processed_ids.json`) for the `status` command. The fetch command derives state from the markdown file directly. |
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

## Viewer (`viewer.html`)

A standalone, self-contained HTML file for browsing exported bookmarks. Opens directly in any browser — no server or build step.

**Architecture:**
- Single file (~30 KB) with inline CSS, JS, and SVG icons
- Client-side markdown parser: line-by-line state machine that reverses the `markdown.py` rendering
- File loading via drag-and-drop or file picker (`FileReader.readAsText()`)
- Rendering pipeline: parse → filter/sort → paginated render (configurable page size: 20/50/100)
- Theme system: CSS custom properties on `[data-theme]` attribute, persisted in `localStorage`
- View mode system: `[data-view]` attribute on `<html>` (`list` or `grid`), persisted in `localStorage`
- Search: pre-computed lowercase text per bookmark, AND logic for multi-word queries, 250ms debounce

**Key patterns:**
- Two render paths (`renderListCard` / `renderGridCard`) with shared helpers (`buildMediaHtml`, `buildBadgesHtml`, `buildLinksHtml`)
- List mode: compact rows with 2-line text clamp, inline media indicators (SVG + count), click-to-expand revealing full media/links
- Grid mode: original card layout with full media grids, show-more text, card footer
- Cards rendered as HTML strings (not DOM nodes) for performance with `innerHTML`
- Pagination system: `goToPage()` → `renderCurrentPage()` → `buildPaginationHtml()` with URL hash persistence (`#page=N`) and keyboard navigation (arrow keys)
- Event delegation on main content for list row expand/collapse (single listener for all cards)
- Event delegation on pagination containers for page button clicks
- Lazy image loading with `loading="lazy"` and `onerror` fallback
- Page size and page position persisted via `localStorage` and URL hash
- No external dependencies — fully offline-capable

## Key Directories

```
src/twitter_bookmarks/    # Source code
tests/                    # Tests with JSON fixtures in tests/fixtures/
.state/                   # Runtime state (gitignored)
~/.config/twitter-bookmarks/  # Config with auth tokens (restricted permissions)
viewer.html               # Standalone bookmarks viewer (client-side only)
```
