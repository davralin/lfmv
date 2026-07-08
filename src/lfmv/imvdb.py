"""IMVDb REST API client.

Uses the official IMVDb API (https://imvdb.com/developers) to search for
music videos and fetch source URLs. Replaces the previous HTML scraping approach.

Workflow:
  1. Search videos by artist name:  GET /api/v1/search/videos?q={name}
  2. Filter results by MusicBrainz slug to ensure correct artist
  3. Fetch source info for each video:  GET /api/v1/video/{id}?include=sources
  4. Construct download URL from source type + ID
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from lfmv import http
from lfmv.config import Config

log = structlog.get_logger(__name__)

IMVDB_API_BASE = "https://imvdb.com/api/v1"
_limiter = http.RateLimiter()
IMVDB_RATE_LIMIT = 1.0

# Source type -> URL template.  yt-dlp also accepts "youtube:{id}" directly.
_SOURCE_URLS: dict[str, str] = {
    "youtube": "https://www.youtube.com/watch?v={}",
    "vimeo": "https://vimeo.com/{}",
}


@dataclass(frozen=True)
class VideoInfo:
    title: str
    year: int | None
    source_url: str
    source_type: str
    source_id: str


def _api_get(
    path: str,
    config: Config,
    *,
    params: dict[str, str | int] | None = None,
) -> httpx.Response:
    """Make an authenticated GET request to the IMVDb API."""
    url = f"{IMVDB_API_BASE}{path}"
    _limiter.wait(IMVDB_RATE_LIMIT)
    return http.get(
        url,
        extra_headers={"IMVDB-APP-KEY": config.imvdb_api_key},
        params=params,
    )


def search_videos(
    name: str,
    config: Config,
    *,
    page: int = 1,
    per_page: int = 50,
) -> list[dict]:
    """Search IMVDb for videos matching the given artist name."""
    try:
        resp = _api_get(
            "/search/videos",
            config,
            params={"q": name, "per_page": per_page, "page": page},
        )
    except httpx.HTTPError as exc:
        log.warning("imvdb_search_error", name=name, error=str(exc))
        return []

    if resp.status_code >= 500:
        log.warning("imvdb_search_server_error", name=name, status=resp.status_code)
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def get_video_sources(video_id: int, config: Config) -> VideoInfo | None:
    """Fetch source information for a single video by ID."""
    try:
        resp = _api_get(f"/video/{video_id}", config, params={"include": "sources"})
    except httpx.HTTPError as exc:
        log.warning("imvdb_video_sources_error", video_id=video_id, error=str(exc))
        return None

    if resp.status_code >= 500:
        log.warning("imvdb_video_sources_server_error", video_id=video_id, status=resp.status_code)
        return None
    if resp.status_code == 404:
        log.warning("imvdb_video_not_found", video_id=video_id)
        return None
    resp.raise_for_status()

    data = resp.json()
    title = data.get("song_title", "")
    year = data.get("year")
    sources: list[dict] = data.get("sources", [])

    for src in sources:
        src_type = src.get("source", "")
        src_id = src.get("source_data", "")
        url = _build_source_url(src_type, src_id)
        if url:
            log.debug(
                "imvdb_source_found",
                video_id=video_id,
                source_type=src_type,
                source_id=src_id,
            )
            return VideoInfo(
                title=title,
                year=year,
                source_url=url,
                source_type=src_type,
                source_id=src_id,
            )

    log.info("imvdb_no_sources", video_id=video_id, title=title)
    return None


def _build_source_url(source_type: str, source_id: str) -> str | None:
    """Construct a full download URL from source type and ID."""
    template = _SOURCE_URLS.get(source_type)
    if template and source_id:
        return template.format(source_id)
    return None


def get_artist_videos(
    name: str,
    slug: str,
    config: Config,
) -> list[VideoInfo]:
    """Search for all videos by an artist and return those with downloadable sources.

    Uses the MusicBrainz slug to filter search results to the correct artist,
    since IMVDb's entity-by-slug endpoint is currently broken (returns 500).

    Returns a list of VideoInfo objects ready for download.
    """
    all_videos: list[dict] = []
    page = 1

    while True:
        results = search_videos(name, config, page=page)
        if not results:
            break
        all_videos.extend(results)
        if len(results) < 50:
            break
        page += 1

    # Filter by slug — only keep videos where the primary artist matches
    filtered = []
    for video in all_videos:
        artists = video.get("artists", [])
        if artists and artists[0].get("slug") == slug:
            filtered.append(video)

    log.info(
        "imvdb_search_results",
        name=name,
        slug=slug,
        total=len(all_videos),
        matched=len(filtered),
    )

    videos: list[VideoInfo] = []
    for video in filtered:
        video_id = video.get("id")
        if not video_id:
            continue
        info = get_video_sources(video_id, config)
        if info:
            videos.append(info)

    log.info("imvdb_videos_with_sources", name=name, count=len(videos))
    return videos
