"""yt-dlp wrapper using it as a Python library (no subprocess)."""

from __future__ import annotations

import re
from pathlib import Path

import structlog
import yt_dlp

from lfmv.config import Config

log = structlog.get_logger(__name__)

# Characters that are unsafe in directory / file names on common filesystems.
# We sanitize the artist name for the directory path we create ourselves;
# yt-dlp handles sanitization of the title inside the template.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str) -> str:
    """Replace filesystem-unsafe characters with an underscore."""
    return _UNSAFE_CHARS.sub("_", name).strip()


def download_video(
    url: str,
    artist_name: str,
    config: Config,
    *,
    dry_run: bool = False,
) -> bool:
    """
    Download a single video URL using yt-dlp.

    The output path is:
        {output_dir}/{artist_name}/{output_template}.%(ext)s

    The per-artist yt-dlp archive file lives at:
        {output_dir}/{artist_name}/.yt-dlp-archive

    Returns True if the download succeeded (or was skipped via archive),
    False on error.
    """
    artist_dir = Path(config.output_dir) / _sanitize(artist_name)
    outtmpl = str(artist_dir / config.output_template) + ".%(ext)s"

    if dry_run:
        log.info("dry_run_skip_download", url=url, artist=artist_name, outtmpl=outtmpl)
        return True

    artist_dir.mkdir(parents=True, exist_ok=True)

    archive_path = artist_dir / ".yt-dlp-archive"

    ydl_opts: dict = {
        "outtmpl": outtmpl,
        "download_archive": str(archive_path),
        # Always merge into mkv for consistent output
        "merge_output_format": "mkv",
        # Metadata sidecars
        "writeinfojson": True,
        "writethumbnail": True,
        # Embed as much as possible into the mkv container
        "embedthumbnail": True,
        "embedsubs": True,
        "subtitleslangs": ["all"],
        "postprocessors": [
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ],
        # Suppress the noisy default progress bars; structlog handles our output
        "quiet": True,
        "no_warnings": False,
        # Geo-bypass attempts
        "geo_bypass": True,
    }

    if config.ytdlp_format:
        ydl_opts["format"] = config.ytdlp_format

    log.info("downloading", url=url, artist=artist_name)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ret = ydl.download([url])
        # yt-dlp returns 0 on success (including archive-skipped)
        if ret != 0:
            log.error("ytdlp_nonzero_return", url=url, artist=artist_name, ret=ret)
            return False
        return True
    except yt_dlp.utils.DownloadError as exc:
        log.error("ytdlp_download_error", url=url, artist=artist_name, error=str(exc))
        return False
    except Exception as exc:
        log.exception("ytdlp_unexpected_error", url=url, artist=artist_name, error=str(exc))
        return False
