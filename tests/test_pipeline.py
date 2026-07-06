"""
Integration tests for the lfmv pipeline.

These tests exercise each stage of the pipeline against live services:
  - Lidarr (local ephemeral container)
  - MusicBrainz (official API, rate-limited)
  - IMVDb (public HTML scraping)

They do NOT download any videos (dry_run=True).

Run with:
    uv run pytest tests/ -m integration -v
"""

from __future__ import annotations

import os

import pytest

import lfmv.lidarr as lidarr_client
from lfmv import imvdb, musicbrainz, pipeline
from lfmv.config import Config
from tests.constants import (
    LIDARR_TEST_API_KEY,
    TEST_ARTIST_IMVDB_SLUG,
    TEST_ARTIST_MBID,
    TEST_ARTIST_NAME,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(lidarr_fixture: dict, tmp_path) -> Config:
    """Build a Config pointing at the test Lidarr instance."""
    os.environ["LIDARR_API_KEY"] = lidarr_fixture["api_key"]
    os.environ["LIDARR_URL"] = lidarr_fixture["url"]
    os.environ["OUTPUT_DIR"] = str(tmp_path)
    return Config.from_env()


# ---------------------------------------------------------------------------
# Stage 1: Lidarr
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_lidarr_fetch_returns_artists(lidarr):
    """Lidarr returns at least one artist (OK Go must be present)."""
    config = _make_config(lidarr, "/tmp")

    artists = lidarr_client.fetch_artists(config)

    assert len(artists) >= 1, "Expected at least one artist from Lidarr"
    names = [a.name for a in artists]
    assert TEST_ARTIST_NAME in names, f"{TEST_ARTIST_NAME!r} not found in {names}"


@pytest.mark.integration
def test_lidarr_artist_has_mbid(lidarr):
    """OK Go's Lidarr entry carries the expected MusicBrainz ID."""
    config = _make_config(lidarr, "/tmp")

    artists = lidarr_client.fetch_artists(config)
    ok_go = next((a for a in artists if a.name == TEST_ARTIST_NAME), None)

    assert ok_go is not None, f"{TEST_ARTIST_NAME!r} not found in Lidarr"
    assert ok_go.mbid == TEST_ARTIST_MBID


# ---------------------------------------------------------------------------
# Stage 2: MusicBrainz  (does not require the Lidarr fixture)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_musicbrainz_resolves_imvdb_slug():
    """OK Go's MBID resolves to the expected IMVDb slug via MusicBrainz."""
    os.environ.setdefault("LIDARR_API_KEY", LIDARR_TEST_API_KEY)
    config = Config.from_env()

    slug = musicbrainz.get_imvdb_slug(TEST_ARTIST_MBID, config)

    assert slug == TEST_ARTIST_IMVDB_SLUG, (
        f"Expected IMVDb slug {TEST_ARTIST_IMVDB_SLUG!r}, got {slug!r}"
    )


@pytest.mark.integration
def test_musicbrainz_unknown_mbid_returns_none():
    """A made-up MBID returns None without raising."""
    os.environ.setdefault("LIDARR_API_KEY", LIDARR_TEST_API_KEY)
    config = Config.from_env()

    slug = musicbrainz.get_imvdb_slug("00000000-0000-0000-0000-000000000000", config)

    assert slug is None


# ---------------------------------------------------------------------------
# Stage 3: IMVDb  (does not require Lidarr)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_imvdb_artist_page_returns_videos():
    """Scraping OK Go's IMVDb page returns at least one video URL."""
    video_urls = imvdb.get_video_page_urls(TEST_ARTIST_IMVDB_SLUG)

    assert len(video_urls) >= 1, "Expected at least one video URL from IMVDb"
    for url in video_urls:
        assert url.startswith("https://imvdb.com/video/"), f"Unexpected URL format: {url!r}"


@pytest.mark.integration
def test_imvdb_video_page_has_source_url():
    """A video detail page yields a VideoInfo with at least one source URL."""
    video_urls = imvdb.get_video_page_urls(TEST_ARTIST_IMVDB_SLUG)
    assert video_urls, "No video URLs scraped — cannot test video detail page"

    info = imvdb.get_video_info(video_urls[0])

    assert info is not None, f"get_video_info returned None for {video_urls[0]}"
    assert info.title, "VideoInfo.title is empty"
    assert info.source_urls, "VideoInfo.source_urls is empty"


@pytest.mark.integration
def test_imvdb_unknown_slug_returns_empty():
    """A non-existent IMVDb slug returns an empty list without raising."""
    urls = imvdb.get_video_page_urls("this-artist-does-not-exist-lfmv-test")
    assert urls == []


# ---------------------------------------------------------------------------
# Stage 4: Full pipeline dry-run
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_pipeline_dry_run(lidarr, tmp_path):
    """
    End-to-end dry run: Lidarr -> MusicBrainz -> IMVDb -> (no download).
    Verifies the pipeline resolves OK Go all the way through without error.
    """
    config = _make_config(lidarr, tmp_path)

    # artist_filter keeps the test focused; avoids hammering MusicBrainz
    # for every artist in the Lidarr instance.
    pipeline.run(config, artist_filter=TEST_ARTIST_NAME, dry_run=True)
