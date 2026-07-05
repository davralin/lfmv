"""Main pipeline: Lidarr -> MusicBrainz -> IMVDb -> yt-dlp."""

from __future__ import annotations

import structlog

from lfmv import __version__
from lfmv.config import Config
from lfmv import downloader, imvdb, lidarr, musicbrainz

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

        # --- Step 3: Scrape IMVDb artist page for video URLs ---
        try:
            video_page_urls = imvdb.get_video_page_urls(slug)
        except Exception:
            artist_log.exception("imvdb_scrape_error", slug=slug)
            skipped += 1
            continue

        if not video_page_urls:
            artist_log.info("no_videos_skipping", slug=slug)
            skipped += 1
            continue

        artist_log.info("processing_videos", slug=slug, video_count=len(video_page_urls))

        # --- Step 4: For each video page, get source URLs and download ---
        for video_url in video_page_urls:
            video_info = None
            try:
                video_info = imvdb.get_video_info(video_url)
            except Exception:
                artist_log.exception("imvdb_video_scrape_error", video_url=video_url)
                failed += 1
                continue

            if video_info is None:
                artist_log.info("no_video_info", video_url=video_url)
                skipped += 1
                continue

            if not video_info.source_urls:
                artist_log.info(
                    "no_source_urls",
                    video_url=video_url,
                    title=video_info.title,
                )
                skipped += 1
                continue

            video_log = artist_log.bind(title=video_info.title, year=video_info.year)

            # Use the first available source URL (usually YouTube)
            source_url = video_info.source_urls[0]
            if len(video_info.source_urls) > 1:
                video_log.debug(
                    "multiple_sources_using_first",
                    sources=video_info.source_urls,
                )

            try:
                ok = downloader.download_video(
                    source_url,
                    artist.name,
                    config,
                    dry_run=dry_run,
                )
            except Exception:
                video_log.exception("download_unexpected_error", url=source_url)
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
