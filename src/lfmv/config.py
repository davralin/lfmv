"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Required environment variable {name!r} is not set")
    return val


def _optional(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _optional_none(name: str) -> str | None:
    return os.environ.get(name) or None


@dataclass(frozen=True)
class Config:
    # Lidarr
    lidarr_url: str
    lidarr_api_key: str

    # Output
    output_dir: str
    # yt-dlp output template relative to the artist directory.
    # The full path will be: {output_dir}/{artist_name}/{output_template}.%(ext)s
    # Default produces: Artist/Title/Title.mkv
    output_template: str

    # yt-dlp
    # None means let yt-dlp choose the best available format
    ytdlp_format: str | None

    # MusicBrainz
    musicbrainz_url: str
    # Seconds to sleep between MusicBrainz requests (official limit: 1/s)
    musicbrainz_rate_limit: float

    # IMVDb
    imvdb_api_key: str

    # Logging
    log_level: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            lidarr_url=_optional("LIDARR_URL", "http://localhost:8686").rstrip("/"),
            lidarr_api_key=_require("LIDARR_API_KEY"),
            output_dir=_optional("OUTPUT_DIR", "/music-videos"),
            output_template=_optional("OUTPUT_TEMPLATE", "%(title)s/%(title)s"),
            ytdlp_format=_optional_none("YTDLP_FORMAT"),
            musicbrainz_url=_optional("MUSICBRAINZ_URL", "https://musicbrainz.org").rstrip("/"),
            musicbrainz_rate_limit=float(_optional("MUSICBRAINZ_RATE_LIMIT", "1.0")),
            imvdb_api_key=_require("IMVDB_API_KEY"),
            log_level=_optional("LOG_LEVEL", "INFO").upper(),
        )
