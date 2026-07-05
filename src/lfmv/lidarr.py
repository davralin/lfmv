"""Lidarr API client."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from lfmv import http
from lfmv.config import Config

log = structlog.get_logger(__name__)

SKIP_ARTISTS = {"Various Artists"}


@dataclass(frozen=True)
class Artist:
    name: str
    mbid: str
    # The path Lidarr uses for this artist on disk (used to derive the
    # sanitized artist name Lidarr would use, not used for our output dir).
    path: str


def fetch_artists(config: Config) -> list[Artist]:
    """Fetch all artists from Lidarr and return those with a valid MBID."""
    url = f"{config.lidarr_url}/api/v1/artist"

    log.info("fetching_artists", url=url)
    try:
        response = http.get(url, extra_headers={"X-Api-Key": config.lidarr_api_key})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to connect to Lidarr at {config.lidarr_url}: {exc}") from exc

    data = response.json()
    artists: list[Artist] = []

    for entry in data:
        name: str = entry.get("artistName", "")
        mbid: str = entry.get("foreignArtistId", "")
        path: str = entry.get("path", "")

        if name in SKIP_ARTISTS:
            log.debug("skipping_artist", reason="blocklist", artist=name)
            continue

        if not mbid:
            log.warning("missing_mbid", artist=name)
            continue

        artists.append(Artist(name=name, mbid=mbid, path=path))

    log.info("artists_loaded", count=len(artists))
    return artists
