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
COPY --from=ghcr.io/astral-sh/uv:0.7.8@sha256:0178a92d156b6f6dbe60e3b52b33b421021f46d634aa9f81f42b91445bb81cdf /uv /usr/local/bin/uv

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
