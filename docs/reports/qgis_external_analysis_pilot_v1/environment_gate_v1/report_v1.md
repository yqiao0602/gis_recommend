# QGIS External Analysis Pilot Environment Gate

Status: `passed`

The pinned environment gate passed on `/home/qy`. No floating image tags were
used and no training rows were emitted.

- Joern image: `ghcr.io/joernio/joern@sha256:27ac49250d279ad9f47d2df9592ffc47a0b10edc2ad1058ad20b48554b18a0d4`
- Joern CLI: `4.0.583`
- Joern Python frontend: generated a non-empty 74,598-byte CPG
- QGIS image: `qgis/qgis@sha256:ac32c27d2fa816f525e3ac264c1c5243454e6f857cb0cfd04345a4e9022fb85c`
- QGIS runtime: `3.28.15`
- DataTrove: `0.9.0` in the isolated Python 3.11 conda environment
- `/home/yll`: mounted read-only and unchanged by the runner

## Registry Recovery

Two independent server pulls of the Joern image previously exhausted their
20-minute windows while retrying the 2,610,138,976-byte layer
`c30c4c54daacfd3c25196cc4013f08b324cdb09fcf38cf767c0d49e72af678e0`.
The same pinned digest was therefore fetched on the workstation as verified OCI
blobs. HTTP/1.1 range requests and aria2 segmentation were used only as the
transport mechanism. The manifest, config, and all three layers were checked
against their declared SHA256 values before ORAS assembled the OCI layout.

Skopeo converted that verified layout to a Docker archive. The archive was
loaded locally, where the image ID matched the config digest
`sha256:915115fa197d5f89ef60d8c0c769531a4aec4cf78c58f82d2a50b51072e80314`.
The 4,155,916,800-byte archive was uploaded as a `.partial` file, verified on
the server, atomically renamed, and loaded. A final pull by the original digest
then reused the local blobs and established the exact RepoDigest.

## Runner Corrections

The live gate exposed two runner assumptions, both reproduced before repair:

- Joern's zstd wrapper requires executable temporary storage, so the parser
  tmpfs is explicitly `rw,exec,nosuid`; the root filesystem and `/home/yll`
  remain read-only.
- `Qgis.QGIS_VERSION` includes the codename (`3.28.15-Firenze`), so the runner
  removes only that suffix and still requires exact numeric version `3.28.15`.
- Joern does not implement `--version`; the runner now extracts the single
  installed `io.joern.joern-cli-*.jar` version and validates a numeric semantic
  version instead of accepting a warning as evidence.

## Evidence

- `run_manifest_v1.json`: `2213dc6d72aab1efc995619da55bac90a1512e2807c7bc44ef4b6e57a26a9c6d`
- `pip_freeze_all.txt`: `c98b391036988d25564fef3579ba657e2a0d7e05b3464d4371690a9ffabf7733`
- server CPG: `2272e05fa8bf2d8aae5f1ee51d457f3671bac6c40539a900dd284f45a767f495`
- server Docker archive: `785824238544ac444ed05368c093334f18032d19ef9de9fdfed28a2d9a5d3b3e`
- final runner: `a74e700ed18508757286f00fc6e804ee1467107cab991b87e4821dad01ffae22`

The earlier timeout logs and failure JSON files remain in this directory as
superseded failure evidence. The next gate is the 20 Processing + 20 API
novelty checkpoint. Task 3 and the 200-source pilot remain unopened until that
checkpoint passes. Formal QGIS training authority, stable124, L3 mapping, and
training admission are unchanged.
