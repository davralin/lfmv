"""yt-dlp wrapper using it as a Python library (no subprocess)."""

from __future__ import annotations

import re
from pathlib import Path

import structlog
import yt_dlp

from lfmv.config import Config

log = structlog.get_logger(__name__)

# Characters that are unsafe in directory / file names on common filesystems.
# We sanitize path segments we provide; yt-dlp handles any placeholders left in the template.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_ALWAYS_CLEAN_EXTENSIONS = (".jpg", ".jpeg", ".webp", ".png", ".mp4", ".webm", ".m4a", ".opus")
_FAILURE_CLEAN_EXTENSIONS = (".mkv", ".part", ".ytdl")
_FRAGMENT_PATTERNS = (".f*.mp4", ".f*.webm", ".f*.m4a", ".f*.opus")


def _sanitize(name: str) -> str:
    """Replace filesystem-unsafe characters with an underscore."""
    return _UNSAFE_CHARS.sub("_", name).strip()


def _cleanup_artifacts(output_base: Path, *, failed: bool) -> None:
    """Remove yt-dlp sidecars/intermediates for one attempted output."""
    candidates = [output_base.with_suffix(ext) for ext in _ALWAYS_CLEAN_EXTENSIONS]
    if failed:
        candidates.extend(output_base.with_suffix(ext) for ext in _FAILURE_CLEAN_EXTENSIONS)

    candidates.extend(
        path
        for pattern in _FRAGMENT_PATTERNS
        for path in output_base.parent.glob(f"{output_base.name}{pattern}")
    )

    for path in candidates:
        if path.exists() and path.is_file():
            try:
                path.unlink()
                log.info("download_artifact_removed", path=str(path), failed=failed)
            except OSError as exc:
                log.warning("download_artifact_cleanup_failed", path=str(path), error=str(exc))


def download_video(
    url: str,
    artist_name: str,
    config: Config,
    *,
    title: str | None = None,
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
    safe_artist = _sanitize(artist_name) or "Unknown Artist"
    artist_dir = Path(config.output_dir) / safe_artist
    if title:
        safe_title = _sanitize(title) or "Unknown Title"
        relative_template = config.output_template.replace("%(title)s", safe_title)
    else:
        relative_template = config.output_template
    output_base = artist_dir / relative_template
    outtmpl = str(output_base) + ".%(ext)s"

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
        # Embed metadata into mkv container
        "embed_infojson": True,
        "writethumbnail": True,
        "embedthumbnail": True,
        "embedsubs": True,
        "subtitleslangs": ["all"],
        "postprocessors": [
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ],
        # Suppress the noisy default progress bars; structlog handles our output
        "nopart": True,
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
            _cleanup_artifacts(output_base, failed=True)
            return False
        _cleanup_artifacts(output_base, failed=False)
        return True
    except yt_dlp.utils.DownloadError as exc:
        log.error("ytdlp_download_error", url=url, artist=artist_name, error=str(exc))
        _cleanup_artifacts(output_base, failed=True)
        return False
    except Exception as exc:
        log.exception("ytdlp_unexpected_error", url=url, artist=artist_name, error=str(exc))
        _cleanup_artifacts(output_base, failed=True)
        return False
