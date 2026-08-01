# Agent instructions for lfmv

## Repository standards

- Read `adr/` before changing workflows, release policy, Renovate, container behavior, or deployment assumptions.
- Treat ADRs as inherited decisions. Do not delete ADRs to make them not apply; add a later ADR that supersedes, narrows, or marks a decision not applicable.
- Keep Git history and commit messages aligned with ADR 0002: linear history and Conventional Commits.
- The active default is a single-image workflow. Multiple deployable images require a repo-specific ADR explaining separate process responsibilities.
- Keep normal GitHub Actions digest-pinned. Keep the SLSA generator workflow tag-pinned as documented in ADR 0003.
- Keep Renovate behavior aligned with ADR 0005 and the existing commit naming style.
- Target Kubernetes PSA `restricted` for workload guidance unless a later ADR documents an exception.

## CI / GitHub Actions

### SHA pinning
All third-party actions in all workflows must be pinned to a commit
SHA with a version comment:

```yaml
uses: docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9  # v3
```

When bumping an action version, resolve the new commit SHA:

```sh
curl -sf "https://api.github.com/repos/<owner>/<action>/tags?per_page=5"
```

Update both the SHA and the version comment.

### CI vs Release split
Two workflows build container images with different attestation levels:

- **`ci.yml`** — triggered on push to `main` and PRs. Builds test images
  tagged `:latest`, `:main`, and `:sha-xxxxx` **without** SLSA provenance or
  SBOM (fast builds). Trivy scans run. No git tags are created.
- **`release.yml`** — triggered on schedule (Monday 09:00 UTC) or
  `workflow_dispatch`. Builds attested images with full SLSA L3 provenance +
  SBOM, tagged with the CalVer date (`YYYY.MM.DD`) and `:latest`. Pushes the
  CalVer git tag and creates the GitHub Release only after image build and
  provenance generation succeed. Vulnerability scans publish SARIF but are
  advisory by default.

### slsa-github-generator — tag pin exception
`slsa-framework/slsa-github-generator` **must** be pinned by version tag, not SHA:

```yaml
uses: slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@v2.1.0
```

The generator embeds the `workflow_ref` from its OIDC token into the provenance
certificate. `slsa-verifier` expects a versioned tag in that claim; a SHA pin
produces a non-verifiable certificate. Do not "fix" this to a SHA.

### provenance job
The `provenance` job exists only in `release.yml`. It is a reusable workflow
call (`uses:`) and cannot contain `steps:`. All image-build logic belongs in the
`image` job, which exposes its registry digest via `outputs.digest`.

### Trivy policy
`severity: CRITICAL,HIGH`, `ignore-unfixed: true`. Trivy scans publish SARIF
for GitHub code scanning, but do not set `exit-code: '1'`; vulnerability
tracking is handled through SARIF alerts rather than blocking PRs/releases.

### Weekly scan
`weekly-scan.yml` scans `ghcr.io/davralin/lfmv:latest` every Sunday 09:00 UTC.
It is independent of the release workflow and does not gate Monday's release.

### SBOM
`sbom: true` on `docker/build-push-action` generates a Syft SBOM and attaches it
as an OCI attestation alongside the image in GHCR. Inspect with:

```sh
docker buildx imagetools inspect ghcr.io/davralin/lfmv:main
```

### Containerfile — HEALTHCHECK
Every Containerfile must include a `HEALTHCHECK` instruction. For single-shot
containers, `HEALTHCHECK NONE` is the accepted value.

## Python / tests

### Integration vs unit tests
Integration tests in `tests/test_pipeline.py` require a live Docker-based Lidarr
instance and are marked `@pytest.mark.integration`. Unit tests (`test_imvdb.py`,
`test_config.py`, `test_downloader.py`) require no network or docker.

CI runs only unit tests: `pytest -m "not integration"`.

Integration tests are run manually: `uv run pytest tests/ -m integration -v`.

### Network in tests
Unit tests must not make real network calls. Use JSON fixtures in
`tests/fixtures/` and mock the HTTP calls with `unittest.mock.patch`. Do not
mock the network in integration tests — they exist precisely to exercise real
HTTP paths.

### Adding new modules
New source modules go in `src/lfmv/`. Shared HTTP utilities (rate limiting,
retry, default headers) live in `src/lfmv/http.py` — use `http.get()` rather
than calling `httpx.get()` directly.

## Local validation

- Run `git diff --check` before committing.
- Run `uv run ruff check src/ tests/` after Python changes.
- Run `uv run ruff format --check src/ tests/` after Python changes.
- Run `uv run pytest tests/ -m "not integration" -v` after behavior changes.
- Run `docker build -f Containerfile -t lfmv:local .` after changing `Containerfile` or image workflows when practical.

## Git

- Do not commit, amend, or push unless explicitly requested.
