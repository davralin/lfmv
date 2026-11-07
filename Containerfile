# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
# lfmv - Lidarr FM Music Videos
# Single-shot container: runs the pipeline once and exits.
# Schedule externally via kubernetes CronJob or host cron with `docker run`.

FROM denoland/deno:bin-2.9.1@sha256:978d3d9d73452234f830739773a0a1a7e3b60463da3dfbcd99375e86ac5481e5 AS deno

FROM python:3.15.2-slim@sha256:e97b88e416c3c01eb427b21fd8cd3ebf006e6ee38afcfcc3cae1c54ee2ab0a75 AS base

# ffmpeg is required by yt-dlp to mux audio+video streams
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --no-create-home lfmv

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /usr/local/bin/uv

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
