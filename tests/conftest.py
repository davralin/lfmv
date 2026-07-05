"""
Integration test fixtures.

Requires Docker and docker compose to be available.

Run with:
    uv run pytest tests/ -m integration -v
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx
import pytest

from tests.constants import LIDARR_TEST_API_KEY, TEST_ARTIST_MBID

TESTS_DIR = Path(__file__).parent
LIDARR_URL = "http://localhost:8686"


def _wait_for_lidarr(timeout: int = 120) -> None:
    """Poll Lidarr's /api/v1/system/status until it responds with 200."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(
                f"{LIDARR_URL}/api/v1/system/status",
                headers={"X-Api-Key": LIDARR_TEST_API_KEY},
                timeout=5,
            )
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise TimeoutError(f"Lidarr did not become ready within {timeout}s")


def _configure_lidarr() -> None:
    """Create the root folder Lidarr requires before artists can be added."""
    headers = {"X-Api-Key": LIDARR_TEST_API_KEY, "Content-Type": "application/json"}

    # Root folder lives inside the ephemeral container — no host mount needed
    r = httpx.post(
        f"{LIDARR_URL}/api/v1/rootfolder",
        headers=headers,
        json={"path": "/music"},
        timeout=10,
    )
    r.raise_for_status()


def _add_test_artist() -> dict:
    """
    Add OK Go to Lidarr via the API using their MusicBrainz ID.
    Returns the created artist object.
    """
    headers = {"X-Api-Key": LIDARR_TEST_API_KEY, "Content-Type": "application/json"}

    # Lidarr's lookup endpoint queries MusicBrainz under the hood
    r = httpx.get(
        f"{LIDARR_URL}/api/v1/artist/lookup",
        headers=headers,
        params={"term": f"lidarr:{TEST_ARTIST_MBID}"},
        timeout=30,
    )
    r.raise_for_status()
    results = r.json()
    if not results:
        raise RuntimeError(f"Lidarr could not find artist MBID {TEST_ARTIST_MBID}")

    artist_data = results[0]

    # Fetch default quality and metadata profile IDs
    quality_profile_id = httpx.get(
        f"{LIDARR_URL}/api/v1/qualityprofile", headers=headers, timeout=10
    ).raise_for_status().json()[0]["id"]

    metadata_profile_id = httpx.get(
        f"{LIDARR_URL}/api/v1/metadataprofile", headers=headers, timeout=10
    ).raise_for_status().json()[0]["id"]

    artist_data["rootFolderPath"] = "/music"
    artist_data["qualityProfileId"] = quality_profile_id
    artist_data["metadataProfileId"] = metadata_profile_id
    artist_data["monitored"] = False
    artist_data["addOptions"] = {"monitor": "none", "searchForMissingAlbums": False}

    add_r = httpx.post(
        f"{LIDARR_URL}/api/v1/artist",
        headers=headers,
        json=artist_data,
        timeout=30,
    )
    add_r.raise_for_status()
    return add_r.json()


@pytest.fixture(scope="session")
def lidarr(tmp_path_factory):
    """
    Session-scoped fixture that:
    1. Starts the Lidarr container via docker compose (API key set via env)
    2. Waits for Lidarr to become ready
    3. Creates a root folder
    4. Adds OK Go as the test artist
    5. Yields a dict with url and api_key
    6. Tears down the container on exit
    """
    compose_file = TESTS_DIR / "docker-compose.yml"

    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d", "--wait"],
        check=True,
    )

    try:
        _wait_for_lidarr()
        _configure_lidarr()
        _add_test_artist()

        yield {"url": LIDARR_URL, "api_key": LIDARR_TEST_API_KEY}
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down", "--volumes", "--remove-orphans"],
            check=False,
        )
