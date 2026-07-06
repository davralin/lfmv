"""CLI entry point for lfmv."""

from __future__ import annotations

import logging
import sys

import click
import structlog

from lfmv import __version__, pipeline
from lfmv.config import Config


def _configure_logging(level: str) -> None:
    """Set up structlog with a human-readable console renderer."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@click.group()
@click.version_option(__version__, prog_name="lfmv")
def cli() -> None:
    """lfmv - Lidarr FM Music Videos.

    Downloads music videos for every artist in your Lidarr library by
    resolving Lidarr -> MusicBrainz -> IMVDb -> yt-dlp.
    """


@cli.command()
@click.option(
    "--artist",
    default=None,
    metavar="NAME",
    help="Only process artists whose name contains NAME (case-insensitive).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Resolve the full pipeline without downloading any videos.",
)
def run(artist: str | None, dry_run: bool) -> None:
    """Execute the lfmv pipeline once and exit."""
    try:
        config = Config.from_env()
    except RuntimeError as exc:
        click.echo(f"Configuration error: {exc}", err=True)
        sys.exit(1)

    _configure_logging(config.log_level)

    pipeline.run(config, artist_filter=artist, dry_run=dry_run)


if __name__ == "__main__":
    cli()
