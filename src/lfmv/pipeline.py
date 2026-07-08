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
            skipped += 1
            continue

        # --- Step 3: Search IMVDb for videos with sources ---
        try:
            videos = imvdb.get_artist_videos(artist.name, slug, config)
        except Exception:
            artist_log.exception("imvdb_search_error", slug=slug)
            skipped += 1
            continue

        if not videos:
            artist_log.info("no_videos_skipping", slug=slug)
            skipped += 1
            continue

        artist_log.info("processing_videos", slug=slug, video_count=len(videos))

        # --- Step 4: Download each video ---
        for video in videos:
            video_log = artist_log.bind(title=video.title, year=video.year)

            try:
                ok = downloader.download_video(
                    video.source_url,
                    artist.name,
                    config,
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
