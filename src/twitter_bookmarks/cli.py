"""CLI interface for twitter-bookmarks.

Commands:
    setup   - Configure Twitter auth credentials
    fetch   - Fetch bookmarks and save to markdown
    status  - Show current backup status
"""

import sys
from pathlib import Path

import click

from .config import (
    CONFIG_FILE,
    AppConfig,
    AuthConfig,
    config_exists,
    load_config,
    save_config,
)
from .logging_config import setup_logging


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--config", type=click.Path(), default=None, help="Config file path")
@click.pass_context
def main(ctx, verbose, config):
    """Twitter/X Bookmarks Backup — Save your bookmarks to markdown."""
    setup_logging(debug=verbose)
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = Path(config) if config else CONFIG_FILE


@main.command()
@click.option(
    "--query-id-only",
    is_flag=True,
    help="Only update the GraphQL query ID (keep existing auth)",
)
@click.pass_context
def setup(ctx, query_id_only):
    """Configure Twitter authentication credentials."""
    config_path = ctx.obj["config_path"]

    if query_id_only:
        if not config_exists(config_path):
            click.echo("Error: No config found. Run setup without --query-id-only first.", err=True)
            sys.exit(1)
        config = load_config(config_path)
        click.echo("Update GraphQL Query ID")
        click.echo("=" * 40)
        click.echo("Open x.com/i/bookmarks → DevTools → Network → filter 'Bookmarks'")
        click.echo("Copy the ID between /graphql/ and /Bookmarks in the request URL.")
        click.echo()
        query_id = click.prompt("query_id")
        config.query_id = query_id
        save_config(config, config_path)
        click.echo(f"\nQuery ID updated in {config_path}")
        return

    click.echo("Twitter Bookmarks Backup — Setup")
    click.echo("=" * 40)
    click.echo()
    click.echo("You need your Twitter/X session cookies.")
    click.echo("To get them:")
    click.echo("  1. Open x.com in your browser and log in")
    click.echo("  2. Open DevTools (F12) -> Application -> Cookies -> https://x.com")
    click.echo("  3. Copy the values of 'auth_token' and 'ct0'")
    click.echo()

    auth_token = click.prompt("auth_token", hide_input=True)
    ct0 = click.prompt("ct0", hide_input=True)

    click.echo()
    click.echo("(Optional) GraphQL query ID — press Enter to skip and use default.")
    click.echo("If you get 404 errors, you'll need to provide this.")
    query_id = click.prompt("query_id", default="", show_default=False)

    config = AppConfig(
        auth=AuthConfig(auth_token=auth_token, ct0=ct0),
        query_id=query_id or None,
    )

    save_config(config, config_path)
    click.echo(f"\nConfig saved to {config_path}")
    click.echo("Run 'twitter-bookmarks fetch' to download your bookmarks.")


@main.command()
@click.option("--full", is_flag=True, help="Re-fetch all (ignore state)")
@click.option("--max-pages", default=50, help="Maximum pages to fetch")
@click.option("-o", "--output", type=click.Path(), default=None, help="Output file")
@click.option(
    "-n", "--count", type=int, default=None, help="Number of latest bookmarks to fetch"
)
@click.option(
    "--delay", type=float, default=None, help="Delay in seconds between API requests"
)
@click.option(
    "--since",
    type=str,
    default=None,
    help="Only include bookmarks after this date (YYYY-MM-DD) in output",
)
@click.option(
    "--dump-raw",
    type=click.Path(),
    default=None,
    help="Save raw API JSON response to file for debugging",
)
@click.pass_context
def fetch(ctx, full, max_pages, output, count, delay, since, dump_raw):
    """Fetch bookmarks and save to markdown."""
    import json as json_mod
    from datetime import datetime, timezone

    config_path = ctx.obj["config_path"]
    if not config_exists(config_path):
        click.echo(
            "Error: No config found. Run 'twitter-bookmarks setup' first.",
            err=True,
        )
        sys.exit(1)

    config = load_config(config_path)
    output_path = Path(output) if output else config.bookmarks_file

    # Lazy imports so --help stays fast
    from .client import TwitterClient
    from .markdown import (
        extract_ids_from_markdown,
        extract_latest_date,
        render_bookmarks_file,
        strip_legacy_headers,
    )
    from .parser import parse_bookmarks
    from .state import StateManager

    state = StateManager(config.state_dir)

    if full:
        click.echo("Full fetch mode — ignoring previous state.")
        state.reset()

    # Parse --since date
    since_date: datetime | None = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            click.echo("Error: --since must be in YYYY-MM-DD format.", err=True)
            sys.exit(1)

    # ── Derive early-stop parameters from existing markdown ──
    existing_content = ""
    known_ids: set[str] = set()
    auto_since: datetime | None = None

    if not full and output_path.exists():
        existing_content = output_path.read_text(encoding="utf-8")
        known_ids = extract_ids_from_markdown(existing_content)
        if known_ids:
            click.echo(f"Found {len(known_ids)} existing bookmarks in {output_path.name}")
        if not since_date:
            auto_since = extract_latest_date(existing_content)
            if auto_since:
                click.echo(
                    f"Auto-detected latest bookmark date: "
                    f"{auto_since.strftime('%Y-%m-%d %H:%M UTC')}"
                )

    early_stop_date = since_date or auto_since
    early_stop_ids = known_ids if known_ids else None

    # Resolve delay: CLI flag > config > 0 (no delay)
    effective_delay = delay if delay is not None else config.fetch_delay

    # ── Fetch from Twitter API ──
    click.echo("Fetching bookmarks from Twitter/X...")
    try:
        with TwitterClient(
            config.auth.auth_token,
            config.auth.ct0,
            query_id=config.query_id,
            capture_raw=bool(dump_raw),
        ) as client:
            raw_entries = client.fetch_all_bookmarks(
                max_pages=max_pages,
                delay=effective_delay,
                max_count=count,
                known_ids=early_stop_ids,
                since_date=early_stop_date,
            )

            # Dump raw API responses for debugging
            if dump_raw:
                dump_path = Path(dump_raw)
                dump_data = {
                    "raw_api_responses": client.raw_responses,
                    "raw_entries": raw_entries,
                }
                dump_path.write_text(
                    json_mod.dumps(dump_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                click.echo(f"Raw API response saved to {dump_path}")

    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Fetched {len(raw_entries)} raw entries.")

    # Parse into structured data
    new_bookmarks = parse_bookmarks(raw_entries)
    if count is not None:
        new_bookmarks = new_bookmarks[:count]
    click.echo(f"Parsed {len(new_bookmarks)} valid bookmarks.")

    if full:
        # ── Full mode: render everything, overwrite ──
        markdown = render_bookmarks_file(new_bookmarks)
        output_path.write_text(markdown, encoding="utf-8")
        click.echo(f"Wrote {len(new_bookmarks)} bookmarks to {output_path}")

        state.mark_all_processed(new_bookmarks)
        state.save()
        return

    # ── Incremental mode: dedup, prepend new ──
    truly_new = [b for b in new_bookmarks if b.tweet_id not in known_ids]

    # Apply --since filter to truly-new bookmarks
    if since_date:
        truly_new = [b for b in truly_new if b.created_at >= since_date]
        click.echo(
            f"Filtered to {len(truly_new)} bookmarks after {since}."
        )

    if not truly_new:
        click.echo("No new bookmarks since last fetch.")
        state.mark_all_processed(new_bookmarks)
        state.save()
        return

    click.echo(f"{len(truly_new)} new bookmarks.")

    # Render only the new bookmarks (newest first)
    new_markdown = render_bookmarks_file(truly_new)

    # Strip legacy headers from existing content before prepending
    cleaned_existing = strip_legacy_headers(existing_content)

    # Prepend new + existing
    if cleaned_existing.strip():
        combined = new_markdown + "\n" + cleaned_existing
    else:
        combined = new_markdown

    output_path.write_text(combined, encoding="utf-8")
    click.echo(
        f"Prepended {len(truly_new)} new bookmarks to {output_path}"
    )

    state.mark_all_processed(new_bookmarks)
    state.save()


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None, help="Output CSV file path")
def convert(input_file, output):
    """Convert a bookmarks markdown file to CSV.

    INPUT_FILE is the path to the markdown file to convert.
    If -o is not specified, CSV is written to stdout.
    """
    from .converter import bookmarks_to_csv
    from .markdown import parse_markdown_to_bookmarks

    input_path = Path(input_file)
    content = input_path.read_text(encoding="utf-8")
    bookmarks = parse_markdown_to_bookmarks(content)

    if not bookmarks:
        click.echo("Error: No bookmarks found in input file.", err=True)
        sys.exit(1)

    click.echo(f"Parsed {len(bookmarks)} bookmarks.", err=True)

    if output:
        output_path = Path(output)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            bookmarks_to_csv(bookmarks, f)
        click.echo(f"CSV written to {output_path}", err=True)
    else:
        csv_content = bookmarks_to_csv(bookmarks)
        click.echo(csv_content, nl=False)


@main.command()
@click.pass_context
def status(ctx):
    """Show current backup status."""
    config_path = ctx.obj["config_path"]
    has_config = config_exists(config_path)

    click.echo("Twitter Bookmarks Backup — Status")
    click.echo("=" * 40)
    click.echo(f"Config: {'Found' if has_config else 'Not configured'} ({config_path})")

    if not has_config:
        click.echo("\nRun 'twitter-bookmarks setup' to get started.")
        return

    config = load_config(config_path)

    from .state import StateManager

    state = StateManager(config.state_dir)
    click.echo(f"Processed bookmarks: {state.count}")
    click.echo(f"Output file: {config.bookmarks_file}")

    if config.bookmarks_file.exists():
        size = config.bookmarks_file.stat().st_size
        click.echo(f"Output file size: {size:,} bytes")
    else:
        click.echo("Output file: Not yet created")
