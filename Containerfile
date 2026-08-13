# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
# lfmv - Lidarr FM Music Videos
# Single-shot container: runs the pipeline once and exits.
# Schedule externally via kubernetes CronJob or host cron with `docker run`.

FROM denoland/deno:bin-2.9.1@sha256:978d3d9d73452234f830739773a0a1a7e3b60463da3dfbcd99375e86ac5481e5 AS deno

FROM python:3.14.7-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS base

# ffmpeg is required by yt-dlp to mux audio+video streams
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --no-create-home lfmv

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.12.4@sha256:d0a6eca6c669dc7e9c51218707b8438a3d30402733d739dcc00adb3e213e8f5c /uv /usr/local/bin/uv

# Install deno JS runtime (required by yt-dlp for YouTube extraction)
COPY --from=deno /deno /usr/local/bin/deno

WORKDIR /app

# Application source and dependencies
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev --no-editable

# Run as non-root
RUN chown -R lfmv /app
USER lfmv

# Default output mount point
VOLUME ["/music-videos"]

# Single-shot container: health checks are not applicable
HEALTHCHECK NONE

# Dependencies and app are already installed in .venv; run directly
ENTRYPOINT ["/app/.venv/bin/python", "-m", "lfmv"]
CMD ["run"]
