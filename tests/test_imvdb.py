"""Unit tests for IMVDb REST API client (no network required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from lfmv.config import Config
from lfmv.imvdb import (
    VideoInfo,
    _build_source_url,
    get_artist_videos,
    get_video_sources,
    search_videos,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read_json(name: str) -> dict:
    import json

    return json.loads((FIXTURES / name).read_text())


def _make_config() -> Config:
    return Config(
        lidarr_url="http://localhost:8686",
        lidarr_api_key="key",
        output_dir="/tmp",
        output_template="%(title)s/%(title)s",
        ytdlp_format=None,
        musicbrainz_url="https://musicbrainz.org",
        musicbrainz_rate_limit=1.0,
        imvdb_api_key="testkey",
        imvdb_rate_limit=0.1,
        log_level="INFO",
    )


def _mock_response(data: dict | list, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


class TestBuildSourceUrl:
    def test_youtube(self):
        url = _build_source_url("youtube", "dTAAsCNK7RA")
        assert url == "https://www.youtube.com/watch?v=dTAAsCNK7RA"

    def test_vimeo(self):
        url = _build_source_url("vimeo", "12345")
        assert url == "https://vimeo.com/12345"

    def test_unknown_returns_none(self):
        assert _build_source_url("dailymotion", "abc") is None

    def test_empty_source_id_returns_none(self):
        assert _build_source_url("youtube", "") is None

    def test_empty_source_type_returns_none(self):
        assert _build_source_url("", "abc") is None


class TestSearchVideos:
    @patch("lfmv.imvdb._api_get")
    def test_returns_results(self, mock_get):
        data = _read_json("imvdb_search_ok-go.json")
        mock_get.return_value = _mock_response(data)

        results = search_videos("OK Go", _make_config())

        assert len(results) == 2
        assert results[0]["song_title"] == "Here It Goes Again"
        mock_get.assert_called_once()

    @patch("lfmv.imvdb._api_get")
    def test_empty_search_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response({"results": []})

        results = search_videos("Unknown Artist", _make_config())
        assert results == []


class TestGetVideoSources:
    @patch("lfmv.imvdb._api_get")
    def test_extracts_youtube_source(self, mock_get):
        data = _read_json("imvdb_video_sources.json")
        mock_get.return_value = _mock_response(data)

        info = get_video_sources(458160868720, _make_config())

        assert info is not None
        assert info.title == "Here It Goes Again"
        assert info.year == 2006
        assert info.source_url == "https://www.youtube.com/watch?v=dTAAsCNK7RA"
        assert info.source_type == "youtube"
        assert info.source_id == "dTAAsCNK7RA"

    @patch("lfmv.imvdb._api_get")
    def test_no_sources_returns_none(self, mock_get):
        data = {"sources": [], "song_title": "Some Song", "year": 2020}
        mock_get.return_value = _mock_response(data)

        info = get_video_sources(999999, _make_config())
        assert info is None

    @patch("lfmv.imvdb._api_get")
    def test_404_returns_none(self, mock_get):
        mock_get.return_value = _mock_response({}, status_code=404)

        info = get_video_sources(999999, _make_config())
        assert info is None


class TestGetArtistVideos:
    @patch("lfmv.imvdb.get_video_sources")
    @patch("lfmv.imvdb.search_videos")
    def test_filters_by_slug(self, mock_search, mock_sources):
        mock_search.return_value = [
            {
                "id": 111,
                "song_title": "Song A",
                "artists": [{"slug": "ok-go"}],
            },
            {
                "id": 222,
                "song_title": "Song B",
                "artists": [{"slug": "other-artist"}],
            },
        ]
        mock_sources.return_value = VideoInfo(
            title="Song A",
            year=2020,
            source_url="https://youtube.com/watch?v=abc",
            source_type="youtube",
            source_id="abc",
        )

        config = _make_config()
        videos = get_artist_videos("OK Go", "ok-go", config)

        assert len(videos) == 1
        assert videos[0].title == "Song A"
        mock_sources.assert_called_once_with(111, config)

    @patch("lfmv.imvdb.search_videos")
    def test_empty_search_returns_empty(self, mock_search):
        mock_search.return_value = []
        videos = get_artist_videos("Unknown", "unknown", _make_config())
        assert videos == []

    @patch("lfmv.imvdb.get_video_sources")
    @patch("lfmv.imvdb.search_videos")
    def test_skips_videos_without_sources(self, mock_search, mock_sources):
        mock_search.return_value = [
            {"id": 111, "song_title": "Song A", "artists": [{"slug": "ok-go"}]},
        ]
        mock_sources.return_value = None

        videos = get_artist_videos("OK Go", "ok-go", _make_config())
        assert videos == []
