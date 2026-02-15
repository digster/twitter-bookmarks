# Prompts

## 2025-02-11
- Build an app similar to https://github.com/alexknowshtml/smaug. Main purpose is to backup bookmarks in markdown. Keep it simple and initially only build the functionality to backup the bookmarks in markdown.

## 2026-02-11
- Add configurable delay between API pagination requests (default 2s, via config and --delay flag) and a --count/-n flag to fetch only the N most recent bookmarks.
- Fix "Unknown" author usernames: add resilient multi-path user extraction (`_extract_user()` with 4 fallback paths), `--dump-raw` diagnostic flag, and debug logging for key visibility.
- Build a standalone HTML viewer (`viewer.html`) for browsing exported bookmarks visually. Single file, no server needed. Features: drag-and-drop file loading, card-based UI with date grouping, full-text search (AND logic), sort toggle, dark/light theme with persistence, photo grids, video thumbnails, reply/quote badges, infinite scroll, responsive layout, keyboard shortcuts.
- Add list view mode to the bookmarks viewer. Compact single-column rows with inline metadata, 2-line text clamp, media indicators, click-to-expand. List mode is the default. Toggle between list/grid via header button. View mode persists in localStorage.
- Fix list view UX: constrain tweet width to ~650px centered, bound expanded images to 500px max, add thumbnail previews in collapsed list cards (photo/video with count badge and play overlay). Thumbnail hides on expand. Responsive for mobile.
- Replace infinite scroll with numbered pagination. Prev/next controls, page numbers with ellipsis, page-size dropdown (20/50/100), URL hash persistence (#page=N), keyboard navigation (arrow keys), date group continuation labels. Page size persists in localStorage.

## 2026-02-14
- Implement incremental bookmark fetching: early-stop pagination (known IDs + date cutoff), JSON bookmark store with merge, --since YYYY-MM-DD filter, auto-detect latest date from output file.
- Fix incremental fetch: make bookmarks.md the source of truth. Remove JSON bookmark store. Derive known_ids and latest_date from markdown. Prepend-only flow for incremental mode. Remove header/date-group lines from output. Add `- **ID:** {tweet_id}` to each entry. Update viewer to derive dateGroup from date and parse ID line.
