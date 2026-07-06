# syntax=docker/dockerfile:1
# lfmv - Lidarr FM Music Videos
# Single-shot container: runs the pipeline once and exits.
# Schedule externally via kubernetes CronJob or host cron with `docker run`.

FROM python:3.13.5-slim@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS base

# ffmpeg is required by yt-dlp to mux audio+video streams
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer (cached as long as pyproject.toml / uv.lock don't change)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-editable

# Application source
COPY src/ src/

# Default output mount point
VOLUME ["/music-videos"]

# Run the pipeline once and exit
ENTRYPOINT ["uv", "run", "--no-dev", "python", "-m", "lfmv"]
CMD ["run"]
