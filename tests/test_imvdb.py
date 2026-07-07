"""Unit tests for IMVDb HTML parsing (no network required)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from lfmv.imvdb import _parse_video_info, _parse_video_page_urls

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestParseVideoPageUrls:
    def test_returns_full_urls_for_matching_artist(self):
        urls = _parse_video_page_urls(_read("imvdb_artist_ok-go.html"), "ok-go")
        assert "https://imvdb.com/video/ok-go/here-it-goes-again" in urls
        assert "https://imvdb.com/video/ok-go/get-over-it" in urls

    def test_deduplicates_hrefs(self):
        urls = _parse_video_page_urls(_read("imvdb_artist_ok-go.html"), "ok-go")
        assert urls.count("https://imvdb.com/video/ok-go/here-it-goes-again") == 1

    def test_excludes_other_artist_links(self):
        urls = _parse_video_page_urls(_read("imvdb_artist_ok-go.html"), "ok-go")
        assert not any("other-artist" in u for u in urls)

    def test_empty_page_returns_empty_list(self):
        assert _parse_video_page_urls("<html><body></body></html>", "ok-go") == []


class TestParseVideoInfo:
    def test_extracts_title_and_year(self):
        info = _parse_video_info(_read("imvdb_video_here-it-goes-again.html"))
        assert info is not None
        assert info.title == "Here It Goes Again"
        assert info.year == "2006"

    def test_extracts_external_source_urls(self):
        info = _parse_video_info(_read("imvdb_video_here-it-goes-again.html"))
        assert info is not None
        assert "https://www.youtube.com/watch?v=dTAAsCNK7RA" in info.source_urls
        assert "https://vimeo.com/12345" in info.source_urls

    def test_filters_imvdb_source_urls(self):
        info = _parse_video_info(_read("imvdb_video_here-it-goes-again.html"))
        assert info is not None
        assert not any(urlparse(u).hostname in ("imvdb.com", "www.imvdb.com") for u in info.source_urls)

    def test_filters_relative_source_urls(self):
        info = _parse_video_info(_read("imvdb_video_here-it-goes-again.html"))
        assert info is not None
        assert not any(u.startswith("/") for u in info.source_urls)

    def test_no_year_returns_none_for_year(self):
        info = _parse_video_info(_read("imvdb_video_no_year.html"))
        assert info is not None
        assert info.title == "Get Over It"
        assert info.year is None

    def test_no_sources_returns_empty_list(self):
        info = _parse_video_info(_read("imvdb_video_no_sources.html"))
        assert info is not None
        assert info.title == "Some Song"
        assert info.source_urls == []

    def test_no_title_returns_none(self):
        assert _parse_video_info(_read("imvdb_video_no_title.html")) is None
