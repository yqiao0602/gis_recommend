"""Package the Gate 2 exclusion authority as a canonical gzip release asset."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = (
    ROOT / "benchmarks/qgis_planner_v1/authority/source_exclusion_ledger.jsonl"
)
DEFAULT_MANIFEST = (
    ROOT
    / "benchmarks/qgis_planner_v1/authority/source_exclusion_ledger_manifest_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "benchmarks/qgis_planner_v1/dist/"
    "qgis-planner-benchmark-v1.0.0-source-exclusion-b6202e4b.jsonl.gz"
)
CHUNK_SIZE = 1024 * 1024
GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff"


def _inspect_raw(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    byte_count = 0
    contains_crlf = False
    previous = b""
    terminal_byte = b""
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
            byte_count += len(chunk)
            if b"\r\n" in previous + chunk:
                contains_crlf = True
            previous = chunk[-1:]
            terminal_byte = chunk[-1:]
    return {
        "sha256": digest.hexdigest(),
        "byte_count": byte_count,
        "contains_crlf": contains_crlf,
        "terminal_newline": terminal_byte == b"\n",
    }


def _write_canonical_gzip(source_path: Path, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    compressed_hash = hashlib.sha256()
    compressed_size = 0
    raw_crc = 0
    raw_size = 0

    def write_chunk(target: Any, data: bytes) -> None:
        nonlocal compressed_size
        target.write(data)
        compressed_hash.update(data)
        compressed_size += len(data)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output_path.parent, prefix=output_path.name + ".", delete=False
        ) as target:
            temporary_path = Path(target.name)
            write_chunk(target, GZIP_HEADER)
            compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
            with source_path.open("rb") as source:
                while chunk := source.read(CHUNK_SIZE):
                    raw_crc = zlib.crc32(chunk, raw_crc)
                    raw_size = (raw_size + len(chunk)) & 0xFFFFFFFF
                    compressed = compressor.compress(chunk)
                    if compressed:
                        write_chunk(target, compressed)
            write_chunk(target, compressor.flush())
            write_chunk(target, struct.pack("<II", raw_crc & 0xFFFFFFFF, raw_size))
        os.replace(temporary_path, output_path)
    except Exception:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise

    return {
        "compressed_sha256": compressed_hash.hexdigest(),
        "compressed_byte_count": compressed_size,
    }


def package_artifact(
    source_path: Path, output_path: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    """Validate raw authority, write canonical gzip, and return updated manifest."""

    raw = _inspect_raw(source_path)
    artifact = manifest.get("artifact", {})
    if raw["sha256"] != artifact.get("sha256"):
        raise ValueError("raw_sha256_mismatch")
    if raw["byte_count"] != artifact.get("byte_count"):
        raise ValueError("raw_byte_count_mismatch")
    if raw["contains_crlf"] or artifact.get("line_ending") != "LF":
        raise ValueError("raw_line_endings_not_lf")
    if not raw["terminal_newline"] or artifact.get("terminal_newline") is not True:
        raise ValueError("raw_terminal_newline_missing")

    compression = manifest.get("compression", {})
    required_compression = {
        "algorithm": "gzip",
        "level": 9,
        "mtime": 0,
        "filename_header": "",
        "os_header": 255,
    }
    if any(compression.get(key) != value for key, value in required_compression.items()):
        raise ValueError("compression_contract_mismatch")

    packaged = _write_canonical_gzip(source_path, output_path)
    updated = deepcopy(manifest)
    updated["freeze_status"] = "local_packaged_unpublished"
    updated["compression"].update(packaged)
    updated["compression"]["implementation"] = (
        f"CPython zlib {zlib.ZLIB_VERSION}"
    )
    updated["compression"]["decoded_sha256"] = raw["sha256"]
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    updated = package_artifact(args.ledger, args.output, manifest)
    args.manifest.write_bytes(
        (json.dumps(updated, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(
        f"output={args.output} "
        f"bytes={updated['compression']['compressed_byte_count']} "
        f"sha256={updated['compression']['compressed_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
