# lfmv

**Lidarr FM Music Videos** — automatically download music videos for every artist in your Lidarr library.

## Pipeline

```
Lidarr API  →  MusicBrainz  →  IMVDb REST API  →  yt-dlp
```

1. Fetch all artists from Lidarr via its REST API (MusicBrainz IDs)
2. Query MusicBrainz for each artist's URL relationships to find their IMVDb link
3. Search IMVDb API for artist videos and resolve YouTube/Vimeo source URLs
4. Download via yt-dlp (as a library, not subprocess) with full metadata

## Design

- **Read-only** against all external services
- **No local database** — yt-dlp's built-in archive file handles deduplication
- **Archive per artist** — lives inside the artist's output folder; deleting the folder wipes the state cleanly
- **Single-shot container** — runs once and exits; schedule externally via Kubernetes CronJob or host cron
- **MusicBrainz rate limiting** — 1 request/second respected

## Usage

### Docker

```sh
docker run --rm \
  -e LIDARR_URL=http://lidarr:8686 \
  -e LIDARR_API_KEY=your-api-key \
  -e IMVDB_API_KEY=your-imvdb-key \
  -v /path/to/music-videos:/music-videos \
  ghcr.io/davralin/lfmv:latest
```

### Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: lfmv
spec:
  schedule: "0 3 * * 0"   # Sunday 03:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: lfmv
            image: ghcr.io/davralin/lfmv:latest
            env:
            - name: LIDARR_URL
              value: "http://lidarr.media.svc.cluster.local:8686"
            - name: LIDARR_API_KEY
              valueFrom:
                secretKeyRef:
                  name: lidarr-secret
                  key: api-key
            - name: IMVDB_API_KEY
              valueFrom:
                secretKeyRef:
                  name: imvdb-secret
                  key: api-key
            volumeMounts:
            - name: music-videos
              mountPath: /music-videos
          restartPolicy: OnFailure
          volumes:
          - name: music-videos
            persistentVolumeClaim:
              claimName: music-videos-pvc
```

## Verifying the image

Release images are tagged with the CalVer release date (`YYYY.MM.DD`) and
`latest`. Use the immutable date tag when verifying
[SLSA Level 3 provenance](https://slsa.dev) with
[`slsa-verifier`](https://github.com/slsa-framework/slsa-verifier):

```sh
slsa-verifier verify-image ghcr.io/davralin/lfmv:<YYYY.MM.DD> \
  --source-uri github.com/davralin/lfmv \
  --source-tag <YYYY.MM.DD>
```

Or verify the cosign signature directly:

```sh
cosign verify ghcr.io/davralin/lfmv:<YYYY.MM.DD> \
  --certificate-identity-regexp '^https://github.com/davralin/lfmv/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

## Configuration

All configuration is via environment variables.

| Variable | Default | Description |
|---|---|---|
| `LIDARR_URL` | `http://localhost:8686` | Lidarr base URL |
| `LIDARR_API_KEY` | **required** | Lidarr API key |
| `IMVDB_API_KEY` | **required** | IMVDb API key |
| `OUTPUT_DIR` | `/music-videos` | Base directory for downloaded videos |
| `OUTPUT_TEMPLATE` | `%(title)s/%(title)s` | yt-dlp output template, relative to artist directory. Must not be absolute or contain `..`. Full path: `{OUTPUT_DIR}/{artist}/{OUTPUT_TEMPLATE}.%(ext)s` |
| `YTDLP_FORMAT` | *(yt-dlp default)* | yt-dlp format selector (e.g. `bestvideo+bestaudio/best`) |
| `MUSICBRAINZ_URL` | `https://musicbrainz.org` | MusicBrainz mirror URL |
| `MUSICBRAINZ_RATE_LIMIT` | `1.0` | Seconds between MusicBrainz requests |
| `LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Output Structure

```
/music-videos/
├── OK Go/
│   ├── .yt-dlp-archive        # deduplication state for this artist
│   ├── WTF/
│   │   └── WTF.mkv            # video + embedded metadata + thumbnail
│   └── White Knuckles/
│       └── White Knuckles.mkv # video + embedded metadata + thumbnail
└── Linkin Park/
    ├── .yt-dlp-archive
    └── Numb/
        └── Numb.mkv
```

Video metadata (info.json) and thumbnails are embedded inside the `.mkv` container as attachments. This layout is compatible with Jellyfin's Music Videos library type.

## Development

Requires [uv](https://github.com/astral-sh/uv).

```sh
git clone https://github.com/davralin/lfmv
cd lfmv
uv sync

# Run against a real Lidarr instance
LIDARR_URL=http://localhost:8686 LIDARR_API_KEY=xxx IMVDB_API_KEY=xxx uv run python -m lfmv run --dry-run

# Process a single artist only
uv run python -m lfmv run --artist "OK Go" --dry-run
```

## Testing

Integration tests spin up an ephemeral Lidarr container and exercise the full pipeline. Docker is required.

```sh
uv run pytest tests/ -m integration -v
```

Tests cover:
- Lidarr API connectivity and artist fetching
- MusicBrainz MBID → IMVDb slug resolution
- IMVDb search API and video source resolution
- Full pipeline dry-run (Lidarr → MusicBrainz → IMVDb, no actual download)

## Credits

- [Lidarr](https://lidarr.audio/)
- [MusicBrainz](https://musicbrainz.org/)
- [IMVDb](https://imvdb.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [AMVD](https://github.com/RandomNinjaAtk/docker-amvd) — original reference implementation
