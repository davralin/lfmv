"""IMVDb HTML scraper.

IMVDb does not require authentication for public pages. We scrape:
  1. Artist page  https://imvdb.com/n/{slug}
     -> collect all /video/{slug}/{video-slug} hrefs (the videography table)
  2. Video detail page  https://imvdb.com/video/{artist}/{title}
     -> extract the song title, year, and source video URLs
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from lfmv import http

log = structlog.get_logger(__name__)

IMVDB_BASE = "https://imvdb.com"
_RATE_LIMIT = 0.5  # seconds between requests (polite scraping)
_limiter = http.RateLimiter()


@dataclass(frozen=True)
class VideoInfo:
    title: str
    year: str | None
    # One or more source URLs (YouTube, Vimeo, …) from the "Video Sources" section
    source_urls: list[str] = field(default_factory=list)


def _parse_video_page_urls(html: str, slug: str) -> list[str]:
    """Parse an IMVDb artist page and return video detail page URLs for this artist."""
    soup = BeautifulSoup(html, "lxml")
    rel_pattern = re.compile(rf"^/video/{re.escape(slug)}/")
    abs_pattern = re.compile(rf"^https?://(?:www\.)?imvdb\.com/video/{re.escape(slug)}/")
    seen: set[str] = set()
    results: list[str] = []
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if not (rel_pattern.match(href) or abs_pattern.match(href)):
            continue
        # Normalise to absolute URL
        full = urljoin(IMVDB_BASE, href) if href.startswith("/") else href
        if full not in seen:
            seen.add(full)
            results.append(full)
    return results


def _parse_video_info(html: str) -> VideoInfo | None:
    """Parse an IMVDb video detail page. Returns None if title cannot be extracted."""
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.find("h1")
    title = ""
    year: str | None = None
    if h1:
        raw = h1.get_text(separator=" ", strip=True)
        # Format: "Song Title (2004) by Linkin Park"  or just "Song Title (2004)"
        year_match = re.search(r"\((\d{4})\)", raw)
        if year_match:
            year = year_match.group(1)
            title = raw[: year_match.start()].strip()
        else:
            # No year — use the full text up to "by " if present
            by_idx = raw.lower().find(" by ")
            title = raw[:by_idx].strip() if by_idx != -1 else raw.strip()

    if not title:
        return None

    source_urls: list[str] = []
    sources_section = soup.find(id="sources")
    if sources_section:
        for tag in sources_section.find_all("a", href=True):
            href: str = tag["href"]
            parsed_host = urlparse(href).hostname
            if href.startswith("http") and parsed_host not in ("imvdb.com", "www.imvdb.com"):
                source_urls.append(href)
    else:
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            if "Video Sources" in heading.get_text():
                ul = heading.find_next("ul")
                if ul:
                    for tag in ul.find_all("a", href=True):
                        href: str = tag["href"]
                        parsed_host = urlparse(href).hostname
                        if href.startswith("http") and parsed_host not in ("imvdb.com", "www.imvdb.com"):
                            source_urls.append(href)
                break

    return VideoInfo(title=title, year=year, source_urls=source_urls)


def get_video_page_urls(slug: str) -> list[str]:
    """
    Scrape the IMVDb artist page and return the full URLs of all individual
    video detail pages where the artist is credited as the primary artist.

    The videography table lists entries as /video/{artist-slug}/{video-slug}.
    We only collect links that contain the artist slug so we avoid
    "featured on" credits from other artists' videos appearing in the list.
    """
    url = f"{IMVDB_BASE}/n/{slug}"
    log.debug("imvdb_artist_page", url=url)
    _limiter.wait(_RATE_LIMIT)

    try:
        response = http.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            log.warning("imvdb_artist_not_found", slug=slug)
        else:
            log.error("imvdb_http_error", slug=slug, status=exc.response.status_code)
        return []
    except httpx.HTTPError as exc:
        log.error("imvdb_request_failed", slug=slug, error=str(exc))
        return []

    results = _parse_video_page_urls(response.text, slug)
    log.info("imvdb_videos_found", slug=slug, count=len(results))
    return results


def get_video_info(video_url: str) -> VideoInfo | None:
    """
    Scrape a single IMVDb video detail page and return a VideoInfo with
    the song title, year, and all source URLs listed on the page.

    Returns None if the page cannot be fetched or the title cannot be parsed.
    """
    log.debug("imvdb_video_page", url=video_url)
    _limiter.wait(_RATE_LIMIT)

    try:
        response = http.get(video_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("imvdb_video_fetch_failed", url=video_url, error=str(exc))
        return None

    info = _parse_video_info(response.text)
    if info is None:
        log.warning("imvdb_no_title", url=video_url)
        return None

    if not info.source_urls:
        log.info("imvdb_no_sources", url=video_url, title=info.title)

    log.debug("imvdb_video_info", title=info.title, year=info.year, sources=info.source_urls)
    return info
