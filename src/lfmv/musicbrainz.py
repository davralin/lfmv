"""MusicBrainz API client with mandatory rate limiting."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
import structlog

from lfmv import http
from lfmv.config import Config

log = structlog.get_logger(__name__)

_limiter = http.RateLimiter()


def get_imvdb_slug(mbid: str, config: Config) -> str | None:
    """
    Query MusicBrainz for the artist's URL relationships and extract
    the IMVDb slug (the last path component of the IMVDb artist URL).

    Returns None if no IMVDb link is found or the request fails.
    """
    url = f"{config.musicbrainz_url}/ws/2/artist/{mbid}?inc=url-rels&fmt=json"
    log.debug("musicbrainz_lookup", mbid=mbid, url=url)
    _limiter.wait(config.musicbrainz_rate_limit)

    try:
        response = http.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            log.warning("musicbrainz_not_found", mbid=mbid)
        else:
            log.error("musicbrainz_http_error", mbid=mbid, status=exc.response.status_code)
        return None
    except httpx.HTTPError as exc:
        log.error("musicbrainz_request_failed", mbid=mbid, error=str(exc))
        return None

    data = response.json()
    relations: list[dict] = data.get("relations", [])

    for rel in relations:
        url_obj = rel.get("url", {})
        resource: str = url_obj.get("resource", "")
        if urlparse(resource).hostname in ("imvdb.com", "www.imvdb.com"):
            # URL format: https://imvdb.com/n/{slug}
            slug = resource.rstrip("/").rsplit("/", 1)[-1]
            log.debug("imvdb_slug_found", mbid=mbid, slug=slug, url=resource)
            return slug

    log.info("no_imvdb_link", mbid=mbid)
    return None
