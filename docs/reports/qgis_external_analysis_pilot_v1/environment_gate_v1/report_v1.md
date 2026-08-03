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

## Controlled Retry

The same pinned digest was retried after GHCR returned its OCI manifest. The
manifest identifies a 2,610,138,976-byte compressed layer
`c30c4c54daacfd3c25196cc4013f08b324cdb09fcf38cf767c0d49e72af678e0`.
The hardened runner executed detached with its own 1,200-second timeout. It
terminated automatically with exit code 124 at `env-smoke:joern_image_pull`;
both `c30c4c54daac` and `373b3e292b8f` logged retries. The image was not
materialized, no runner or pull process remained, and the pilot directory used
32 KiB. Downstream environment stages therefore remained closed.

Evidence hashes:

- `environment_failure_v1.json`: `1aaaaea0c5a530e89acd10c839fbfe48ff8b9ad97ebbd455932a1b6f964be14b`
- `env-smoke.nohup.log`: `6a891943232f856ceab0eb839ed3ee3af003f32474c7af4bf9652e738a757103`
- `environment_failure_retry_v2.json`: `2c8b8e0ba3ad47ff41707c83352bbb36cba47f33e2caf4631545164017a4906b`
- `env-smoke-retry.nohup.log`: `08557b2eb60445478063e639f5805bb3594a201b8014cb725f584f2dd372d7d3`
