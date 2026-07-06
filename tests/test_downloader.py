"""Unit tests for the yt-dlp wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from lfmv.config import Config
from lfmv.downloader import _sanitize, download_video


def _make_config(tmp_path: Path) -> Config:
    return Config(
        lidarr_url="http://localhost:8686",
        lidarr_api_key="key",
        output_dir=str(tmp_path),
        output_template="%(title)s/%(title)s",
        ytdlp_format=None,
        musicbrainz_url="https://musicbrainz.org",
        musicbrainz_rate_limit=1.0,
        log_level="INFO",
    )


class TestSanitize:
    def test_replaces_unsafe_chars(self):
        assert _sanitize("AC/DC") == "AC_DC"
        assert _sanitize("Artist: Name") == "Artist_ Name"

    def test_strips_surrounding_whitespace(self):
        assert _sanitize("  Artist  ") == "Artist"

    def test_safe_name_unchanged(self):
        assert _sanitize("OK Go") == "OK Go"


class TestDownloadVideo:
    def test_dry_run_returns_true_without_creating_dir(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = download_video("https://youtu.be/x", "OK Go", cfg, dry_run=True)
        assert result is True
        assert not (tmp_path / "OK Go").exists()

    def test_creates_artist_dir_on_real_download(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("yt_dlp.YoutubeDL") as MockYdl:
            MockYdl.return_value.__enter__.return_value.download.return_value = 0
            result = download_video("https://youtu.be/x", "OK Go", cfg)
        assert result is True
        assert (tmp_path / "OK Go").is_dir()

    def test_nonzero_return_yields_false(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("yt_dlp.YoutubeDL") as MockYdl:
            MockYdl.return_value.__enter__.return_value.download.return_value = 1
            result = download_video("https://youtu.be/x", "OK Go", cfg)
        assert result is False

    def test_download_error_yields_false(self, tmp_path):
        import yt_dlp

        cfg = _make_config(tmp_path)
        with patch("yt_dlp.YoutubeDL") as MockYdl:
            MockYdl.return_value.__enter__.return_value.download.side_effect = (
                yt_dlp.utils.DownloadError("network error")
            )
            result = download_video("https://youtu.be/x", "OK Go", cfg)
        assert result is False
