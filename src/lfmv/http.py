"""Shared HTTP utilities: default headers, retry on transient errors, rate limiting."""

from __future__ import annotations

import time

import httpx
import structlog

from lfmv import USER_AGENT

log = structlog.get_logger(__name__)

_DEFAULT_HEADERS: dict[str, str] = {"User-Agent": USER_AGENT}


class RateLimiter:
    """Enforces a minimum gap between calls by tracking the last call time."""

    def __init__(self) -> None:
        self._last: float = 0.0

    def wait(self, seconds: float) -> None:
        """Sleep until at least `seconds` have elapsed since the previous call."""
        elapsed = time.monotonic() - self._last
        remaining = seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last = time.monotonic()


def get(
    url: str,
    *,
    extra_headers: dict[str, str] | None = None,
    params: dict[str, str | int] | None = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> httpx.Response:
    """GET with automatic retry on transient 5xx errors and network errors."""
    headers = {**_DEFAULT_HEADERS, **(extra_headers or {})}
    last_exc: Exception | None = None
    resp: httpx.Response | None = None

    for attempt in range(retries):
        try:
            resp = httpx.get(
                url, headers=headers, params=params, timeout=timeout, follow_redirects=True
            )
            if resp.status_code < 500:
                return resp
            log.warning("http_5xx_retrying", url=url, status=resp.status_code, attempt=attempt + 1)
        except httpx.NetworkError as exc:
            last_exc = exc
            log.warning("http_network_error_retrying", url=url, error=str(exc), attempt=attempt + 1)

        if attempt < retries - 1:
            time.sleep(2**attempt)

    if last_exc:
        raise last_exc
    assert resp is not None
    return resp
