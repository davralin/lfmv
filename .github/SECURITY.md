# Security Policy

## Supported Versions

Only the latest CalVer release is supported with security fixes. No patches are backported to older releases.

## Reporting a Vulnerability

Use [GitHub private vulnerability reporting](https://github.com/davralin/lfmv/security/advisories/new) to disclose security issues confidentially.

Please include a description of the issue, steps to reproduce, and any relevant version information.

## Response

Vulnerability reports are acknowledged within a few days. Critical issues ship as an out-of-cycle release; other issues ship in the next scheduled weekly release (Mondays).

## Release Integrity

All releases carry SLSA Build L3 provenance, verifiable with [`slsa-verifier`](https://github.com/slsa-framework/slsa-verifier):

```
slsa-verifier verify-image ghcr.io/davralin/lfmv:<version> \
  --source-uri github.com/davralin/lfmv \
  --provenance-repository ghcr.io/davralin/lfmv
```
