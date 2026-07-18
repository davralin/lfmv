# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
# lfmv - Lidarr FM Music Videos
# Single-shot container: runs the pipeline once and exits.
# Schedule externally via kubernetes CronJob or host cron with `docker run`.

FROM denoland/deno:bin-2.9.1@sha256:978d3d9d73452234f830739773a0a1a7e3b60463da3dfbcd99375e86ac5481e5 AS deno

FROM python:3.14.6-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6 AS base

# ffmpeg is required by yt-dlp to mux audio+video streams
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --no-create-home lfmv

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc /uv /usr/local/bin/uv

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
