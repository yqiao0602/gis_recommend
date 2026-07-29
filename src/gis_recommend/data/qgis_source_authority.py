"""Canonical source authority for de-duplicating harvested QGIS files."""

from __future__ import annotations

import hashlib
from pathlib import Path


def source_authority(path: Path, *, source_sha256: str) -> dict[str, str]:
    if not path.is_file():
        return {
            "source_authority_key": f"source_sha256:{source_sha256}",
            "source_authority_basis": "source_sha256_fallback",
            "normalized_source_body_sha256": "",
            "upstream_source_repo": "",
            "upstream_source_path": "",
        }
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    upstream_repo = ""
    upstream_path = ""
    body_start = 0
    metadata_found = False
    for index, line in enumerate(lines[:8]):
        if line.startswith("# Source repo:"):
            upstream_repo = line.partition(":")[2].strip()
            metadata_found = True
        elif line.startswith("# Source path:"):
            upstream_path = line.partition(":")[2].strip()
            metadata_found = True
        elif line.startswith("# Query used:") or line.startswith("# Harvested at:"):
            metadata_found = True
        elif metadata_found and not line.strip():
            body_start = index + 1
            break
        elif metadata_found:
            body_start = index
            break
    normalized_body = "\n".join(line.rstrip() for line in lines[body_start:]).strip()
    body_sha = hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
    return {
        "source_authority_key": f"normalized_source_body_sha256:{body_sha}",
        "source_authority_basis": "normalized_source_body_sha256",
        "normalized_source_body_sha256": body_sha,
        "upstream_source_repo": upstream_repo,
        "upstream_source_path": upstream_path,
    }
