# Agent instructions for lfmv

## CI / GitHub Actions

### SHA pinning
All third-party actions in `.github/workflows/ci.yml` must be pinned to a commit
SHA with a version comment:

```yaml
uses: docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9  # v3
```

When bumping an action version, resolve the new commit SHA:

```sh
curl -sf "https://api.github.com/repos/<owner>/<action>/tags?per_page=5"
```

Update both the SHA and the version comment.

### slsa-github-generator — tag pin exception
`slsa-framework/slsa-github-generator` **must** be pinned by version tag, not SHA:

```yaml
uses: slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@v2.1.0
```

The generator embeds the `workflow_ref` from its OIDC token into the provenance
certificate. `slsa-verifier` expects a versioned tag in that claim; a SHA pin
produces a non-verifiable certificate. Do not "fix" this to a SHA.

### provenance job
The `provenance` job is a reusable workflow call (`uses:`). It cannot contain
`steps:`. All image-build logic belongs in the `image` job, which exposes its
registry digest via `outputs.digest`.

### Trivy policy
`severity: CRITICAL,HIGH`, `ignore-unfixed: true`. Do not lower the severity
threshold or remove `exit-code: '1'` — both the config scan and the image scan
must remain blocking.

## Python / tests

### Integration vs unit tests
Integration tests in `tests/test_pipeline.py` require a live Docker-based Lidarr
instance and are marked `@pytest.mark.integration`. Unit tests (`test_imvdb.py`,
`test_config.py`, `test_downloader.py`) require no network or docker.

CI runs only unit tests: `pytest -m "not integration"`.

Integration tests are run manually: `uv run pytest tests/ -m integration -v`.

### Network in tests
Unit tests must not make real network calls. Use HTML fixtures in
`tests/fixtures/` and call the `_parse_*` helpers directly. Do not mock the
network in integration tests — they exist precisely to exercise real HTTP paths.

### Adding new modules
New source modules go in `src/lfmv/`. Shared HTTP utilities (rate limiting,
retry, default headers) live in `src/lfmv/http.py` — use `http.get()` rather
than calling `httpx.get()` directly.
