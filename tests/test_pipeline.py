"""
Integration tests for the lfmv pipeline.

These tests exercise each stage of the pipeline against live services:
  - Lidarr (local ephemeral container)
  - MusicBrainz (official API, rate-limited)
  - IMVDb (REST API)

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


def _make_config(
    *,
    lidarr_url: str = "http://localhost:8686",
    lidarr_api_key: str = LIDARR_TEST_API_KEY,
    output_dir: str = "/tmp",
) -> Config:
    """Build a Config for integration tests without mutating process environment."""
    return Config(
        lidarr_url=lidarr_url,
        lidarr_api_key=lidarr_api_key,
        output_dir=output_dir,
        output_template="%(title)s/%(title)s",
        ytdlp_format=None,
        musicbrainz_url="https://musicbrainz.org",
        musicbrainz_rate_limit=1.0,
        imvdb_api_key=os.environ.get("IMVDB_API_KEY", LIDARR_TEST_API_KEY),
        log_level="INFO",
    )


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------


def test_print_summary_uses_readable_metadata_links(capsys):
    """Metadata contribution links include artist names and avoid direct edit URLs."""
    pipeline._print_summary(
        total=3,
        artists_skipped=2,
        videos_downloaded=1,
        video_downloads_failed=0,
        no_imvdb_link=[("Switch Angel", "add1511e-cac6-4548-9f53-930183cb3eaf")],
        no_videos=[("Alizee", "alizee")],
        few_videos=[("My Dying Bride", "my-dying-bride", 2)],
    )

    output = capsys.readouterr().out

    assert "Missing IMVDb link in MusicBrainz:" in output
    assert (
        "Switch Angel: https://musicbrainz.org/artist/add1511e-cac6-4548-9f53-930183cb3eaf"
    ) in output
    assert "Alizee: https://imvdb.com/n/alizee" in output
    assert "My Dying Bride (2 videos): https://imvdb.com/n/my-dying-bride" in output
    assert "/edit" not in output


# ---------------------------------------------------------------------------
# Stage 1: Lidarr
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_lidarr_fetch_returns_artists(lidarr):
    """Lidarr returns at least one artist (OK Go must be present)."""
    config = _make_config(lidarr_url=lidarr["url"], lidarr_api_key=lidarr["api_key"])

    artists = lidarr_client.fetch_artists(config)

    assert len(artists) >= 1, "Expected at least one artist from Lidarr"
    names = [a.name for a in artists]
    assert TEST_ARTIST_NAME in names, f"{TEST_ARTIST_NAME!r} not found in {names}"


@pytest.mark.integration
def test_lidarr_artist_has_mbid(lidarr):
    """OK Go's Lidarr entry carries the expected MusicBrainz ID."""
    config = _make_config(lidarr_url=lidarr["url"], lidarr_api_key=lidarr["api_key"])

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
    config = _make_config()

    slug = musicbrainz.get_imvdb_slug(TEST_ARTIST_MBID, config)

    assert slug == TEST_ARTIST_IMVDB_SLUG, (
        f"Expected IMVDb slug {TEST_ARTIST_IMVDB_SLUG!r}, got {slug!r}"
    )


@pytest.mark.integration
def test_musicbrainz_unknown_mbid_returns_none():
    """A made-up MBID returns None without raising."""
    config = _make_config()

    slug = musicbrainz.get_imvdb_slug("00000000-0000-0000-0000-000000000000", config)

    assert slug is None


# ---------------------------------------------------------------------------
# Stage 3: IMVDb  (does not require Lidarr)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_imvdb_search_returns_videos():
    """Searching for OK Go on IMVDb returns at least one video."""
    config = _make_config()

    results = imvdb.search_videos("OK Go", config)

    assert len(results) >= 1, "Expected at least one video from IMVDb search"
    for v in results:
        assert "song_title" in v, f"Missing song_title in result: {v}"


@pytest.mark.integration
def test_imvdb_get_artist_videos_returns_sources():
    """Fetching OK Go's videos with sources returns at least one VideoInfo."""
    config = _make_config()

    videos, count = imvdb.get_artist_videos(TEST_ARTIST_NAME, TEST_ARTIST_IMVDB_SLUG, config)

    assert count >= 1, "Expected at least one slug-matched video from IMVDb"
    assert len(videos) >= 1, "Expected at least one video with sources"
    for v in videos:
        assert v.title, "VideoInfo.title is empty"
        assert v.source_url, "VideoInfo.source_url is empty"
        assert v.source_type in ("youtube", "vimeo"), f"Unexpected source_type: {v.source_type}"


@pytest.mark.integration
def test_imvdb_unknown_slug_returns_empty():
    """A non-existent IMVDb slug returns an empty list without raising."""
    config = _make_config()

    videos, count = imvdb.get_artist_videos("Fake Artist", "fake-artist-does-not-exist", config)
    assert videos == []
    assert count == 0


# ---------------------------------------------------------------------------
# Stage 4: Full pipeline dry-run
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_pipeline_dry_run(lidarr, tmp_path):
    """
    End-to-end dry run: Lidarr -> MusicBrainz -> IMVDb -> (no download).
    Verifies the pipeline resolves OK Go all the way through without error.
    """
    config = _make_config(
        lidarr_url=lidarr["url"],
        lidarr_api_key=lidarr["api_key"],
        output_dir=str(tmp_path),
    )

    # artist_filter keeps the test focused; avoids hammering MusicBrainz
    # for every artist in the Lidarr instance.
    pipeline.run(config, artist_filter=TEST_ARTIST_NAME, dry_run=True)
