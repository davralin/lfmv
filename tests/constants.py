"""Shared constants for the integration test suite."""

# Must match LIDARR__AUTH__APIKEY in tests/docker-compose.yml (20+ chars required)
LIDARR_TEST_API_KEY = "lfmvtestkey1234567890"

# OK Go — reliable test artist
# MusicBrainz ID confirmed to have an IMVDb URL relationship
# IMVDb slug: https://imvdb.com/n/ok-go
TEST_ARTIST_MBID = "e132d370-2a59-4437-8610-756df28a5a02"
TEST_ARTIST_NAME = "OK Go"
TEST_ARTIST_IMVDB_SLUG = "ok-go"
