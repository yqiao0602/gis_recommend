# QGIS External Analysis Pilot Environment Gate

Status: `blocked_registry_pull_timeout`

The server environment gate did not pass. The pinned Joern image
`ghcr.io/joernio/joern@sha256:27ac49250d279ad9f47d2df9592ffc47a0b10edc2ad1058ad20b48554b18a0d4`
did not finish pulling from GHCR during a detached 20-minute run. Docker logged a
retry for layer `c30c4c54daac`; the image was not registered locally. The runner
and its pull process were then terminated, and no process was left running.

The runner was hardened after this observation:

- image pulls now have a default 1,200-second timeout;
- `ERR` is inherited inside functions with Bash `errtrace`;
- `INT` and `TERM` produce a structured failure artifact;
- the timeout path was replayed with a one-second bound to verify artifact
  generation, producing `environment_failure_v1.json` with exit code 124 and
  stage `env-smoke:joern_image_pull`.

This is an infrastructure/network gate failure, not a Joern query-quality
result. The QGIS image, DataTrove environment, fixture queries, 40-source
novelty checkpoint, and 200-source pilot were not started. No training rows were
emitted, and no formal QGIS training authority, L3 mapping, or catalog was
modified. Retry must use the same pinned digest after GHCR connectivity is
stable; a floating tag is not an acceptable fallback.

Evidence hashes:

- `environment_failure_v1.json`: `1aaaaea0c5a530e89acd10c839fbfe48ff8b9ad97ebbd455932a1b6f964be14b`
- `env-smoke.nohup.log`: `6a891943232f856ceab0eb839ed3ee3af003f32474c7af4bf9652e738a757103`
