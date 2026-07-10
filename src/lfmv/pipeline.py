"""Main pipeline: Lidarr -> MusicBrainz -> IMVDb -> yt-dlp."""

from __future__ import annotations

import structlog

from lfmv import __version__, downloader, imvdb, lidarr, musicbrainz
from lfmv.config import Config

log = structlog.get_logger(__name__)


def run(
    config: Config,
    *,
    artist_filter: str | None = None,
    dry_run: bool = False,
) -> None:
    """
    Execute the full lfmv pipeline.

    Args:
        config: Loaded configuration.
        artist_filter: If set, only process the artist whose name matches
                       (case-insensitive substring match). Useful for targeted
                       runs and testing.
        dry_run: If True, resolve the full pipeline but skip actual downloads.
    """
    log.info("lfmv_start", version=__version__, dry_run=dry_run)

    # --- Step 1: Fetch artists from Lidarr ---
    try:
        artists = lidarr.fetch_artists(config)
    except RuntimeError as exc:
        log.error("lidarr_fatal", error=str(exc))
        raise SystemExit(1) from exc

    if artist_filter:
        needle = artist_filter.lower()
        artists = [a for a in artists if needle in a.name.lower()]
        if not artists:
            log.warning("artist_filter_no_match", filter=artist_filter)
            return
        log.info("artist_filter_applied", filter=artist_filter, matched=len(artists))

    total = len(artists)
    downloaded = 0
    skipped = 0
    failed = 0
    no_imvdb_link: list[tuple[str, str]] = []
    no_videos: list[tuple[str, str]] = []
    few_videos: list[tuple[str, str, int]] = []

    for idx, artist in enumerate(artists, 1):
        artist_log = log.bind(artist=artist.name, mbid=artist.mbid, progress=f"{idx}/{total}")

        # --- Step 2: Resolve IMVDb slug via MusicBrainz ---
        try:
            slug = musicbrainz.get_imvdb_slug(artist.mbid, config)
        except Exception:
            artist_log.exception("musicbrainz_unexpected_error")
            skipped += 1
            continue

        if not slug:
            artist_log.info("no_imvdb_link_skipping")
            no_imvdb_link.append((artist.name, artist.mbid))
            skipped += 1
            continue

        # --- Step 3: Search IMVDb for videos with sources ---
        try:
            videos, video_count = imvdb.get_artist_videos(artist.name, slug, config)
        except Exception:
            artist_log.exception("imvdb_search_error", slug=slug)
            skipped += 1
            continue

        if video_count == 0:
            artist_log.info("no_videos_skipping", slug=slug)
            no_videos.append((artist.name, slug))
            skipped += 1
            continue

        if video_count < 5:
            few_videos.append((artist.name, slug, video_count))

        artist_log.info("processing_videos", slug=slug, video_count=len(videos))

        # --- Step 4: Download each video ---
        for video in videos:
            video_log = artist_log.bind(title=video.title, year=video.year)

            try:
                ok = downloader.download_video(
                    video.source_url,
                    artist.name,
                    config,
                    title=video.title,
                    dry_run=dry_run,
                )
            except Exception:
                video_log.exception("download_unexpected_error", url=video.source_url)
                failed += 1
                continue

            if ok:
                downloaded += 1
            else:
                failed += 1

    log.info(
        "lfmv_done",
        total_artists=total,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
    )

    _print_summary(total, downloaded, skipped, failed, no_imvdb_link, no_videos, few_videos)


def _print_summary(
    total: int,
    downloaded: int,
    skipped: int,
    failed: int,
    no_imvdb_link: list[tuple[str, str]],
    no_videos: list[tuple[str, str]],
    few_videos: list[tuple[str, str, int]],
) -> None:
    """Print a human-readable summary of the run to stdout."""
    print()
    print("=" * 50)
    print(f"  lfmv run complete - {total} artists processed")
    print(f"  {downloaded} downloaded  |  {skipped} skipped  |  {failed} failed")
    print("=" * 50)

    if no_imvdb_link:
        print()
        print("No IMVDb page found - add to MusicBrainz:")
        for name, mbid in no_imvdb_link:
            print(f"  https://musicbrainz.org/artist/{mbid}/edit")
            print(f"    {name}")

    if no_videos:
        print()
        print("Zero music videos - add to IMVDb:")
        for name, slug in no_videos:
            print(f"  https://imvdb.com/n/{slug}")
            print(f"    {name}")

    if few_videos:
        print()
        print("Fewer than 5 music videos - add more to IMVDb:")
        for name, slug, count in few_videos:
            print(f"  https://imvdb.com/n/{slug}  ({count} videos)")
            print(f"    {name}")

    if not no_imvdb_link and not no_videos and not few_videos:
        print()
        print("All artists have IMVDb pages with 5+ music videos.")

    print()
