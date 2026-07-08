"""Unit tests for Config.from_env()."""

from __future__ import annotations

import pytest

from lfmv.config import Config


def test_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("LIDARR_API_KEY", raising=False)
    monkeypatch.delenv("IMVDB_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="LIDARR_API_KEY"):
        Config.from_env()


def test_defaults(monkeypatch):
    monkeypatch.setenv("LIDARR_API_KEY", "testkey")
    monkeypatch.setenv("IMVDB_API_KEY", "imvdbtestkey")
    for var in [
        "LIDARR_URL",
        "OUTPUT_DIR",
        "OUTPUT_TEMPLATE",
        "YTDLP_FORMAT",
        "MUSICBRAINZ_URL",
        "MUSICBRAINZ_RATE_LIMIT",
        "IMVDB_RATE_LIMIT",
        "LOG_LEVEL",
    ]:
        monkeypatch.delenv(var, raising=False)

    cfg = Config.from_env()
    assert cfg.lidarr_url == "http://localhost:8686"
    assert cfg.lidarr_api_key == "testkey"
    assert cfg.output_dir == "/music-videos"
    assert cfg.output_template == "%(title)s/%(title)s"
    assert cfg.ytdlp_format is None
    assert cfg.musicbrainz_url == "https://musicbrainz.org"
    assert cfg.musicbrainz_rate_limit == 1.0
    assert cfg.imvdb_api_key == "imvdbtestkey"
    assert cfg.log_level == "INFO"


def test_custom_values(monkeypatch):
    monkeypatch.setenv("LIDARR_API_KEY", "mykey")
    monkeypatch.setenv("IMVDB_API_KEY", "myimvdbkey")
    monkeypatch.setenv("LIDARR_URL", "http://lidarr:8686")
    monkeypatch.setenv("OUTPUT_DIR", "/videos")
    monkeypatch.setenv("YTDLP_FORMAT", "bestvideo+bestaudio")
    monkeypatch.setenv("MUSICBRAINZ_RATE_LIMIT", "2.5")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    cfg = Config.from_env()
    assert cfg.lidarr_url == "http://lidarr:8686"
    assert cfg.output_dir == "/videos"
    assert cfg.ytdlp_format == "bestvideo+bestaudio"
    assert cfg.musicbrainz_rate_limit == 2.5
    assert cfg.imvdb_api_key == "myimvdbkey"
    assert cfg.log_level == "DEBUG"


def test_strips_trailing_slash_from_urls(monkeypatch):
    monkeypatch.setenv("LIDARR_API_KEY", "k")
    monkeypatch.setenv("IMVDB_API_KEY", "ik")
    monkeypatch.setenv("LIDARR_URL", "http://localhost:8686/")
    monkeypatch.setenv("MUSICBRAINZ_URL", "https://musicbrainz.org/")

    cfg = Config.from_env()
    assert cfg.lidarr_url == "http://localhost:8686"
    assert cfg.musicbrainz_url == "https://musicbrainz.org"
