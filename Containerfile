# syntax=docker/dockerfile:1
# lfmv - Lidarr FM Music Videos
# Single-shot container: runs the pipeline once and exits.
# Schedule externally via kubernetes CronJob or host cron with `docker run`.

FROM python:3.14.6-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1 AS base

# ffmpeg is required by yt-dlp to mux audio+video streams
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 1000 --no-create-home lfmv

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /usr/local/bin/uv

WORKDIR /app

# Dependency layer (cached as long as pyproject.toml / uv.lock don't change)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-editable

# Application source
COPY src/ src/

# Run as non-root
RUN chown -R lfmv /app
USER lfmv

# Default output mount point
VOLUME ["/music-videos"]

# Run the pipeline once and exit
ENTRYPOINT ["uv", "run", "--no-dev", "python", "-m", "lfmv"]
CMD ["run"]
