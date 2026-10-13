#!/usr/bin/env python3
"""Bounded parser-layer extraction for six priority GEE scripts.

Runs extract_gee_source_evidence() on exactly six raw scripts and writes
per-script AST evidence artifacts for the reconciliation audit. Read-only on
sources; no G0 modification, no full-corpus extraction, no training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parents[1].name == "system_redesign" else Path(__file__).resolve().parent.parent
RAW_DIR = BASE / ".tmp_gee_batch13_sources" / "Data"
SCRIPTS = {
    "script_302840": "data300000/script_302840.txt",
    "script_269131": "data270000/script_269131.txt",
    "script_36595": "data40000/script_36595.txt",
    "script_275285": "data280000/script_275285.txt",
    "script_405410": "data400000/script_405410.txt",
    "script_93009": "data100000/script_93009.txt",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_js(text: str) -> dict[str, Any]:
    """Parse GEE JavaScript into an ESTree-compatible AST.

    Prefers an installed esprima/pyjsparser; raises a clear error when no
    parser backend is available so the audit stays fail-closed.
    """
    try:
        import esprima  # type: ignore
    except ImportError:
        try:
            import pyjsparser  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "no JavaScript parser backend available; install esprima or pyjsparser"
            ) from exc
        return pyjsparser.parse(text)
    return esprima.parseScript(text, loc=True, range=True).toDict()


def extract_evidence(ast: dict[str, Any], *, source_path: str, source_sha256: str) -> Any:
    from gis_recommend.data.gee_source_extractor import extract_gee_source_evidence

    return extract_gee_source_evidence(ast, source_path=source_path, source_sha256=source_sha256)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from gis_recommend.data.gee_source_extractor import EXTRACTOR_VERSION
    except ImportError:
        EXTRACTOR_VERSION = "unknown"
    outputs = {}
    per_script = {}
    for script, relative in sorted(SCRIPTS.items()):
        raw_path = args.raw_dir / relative
        raw_bytes = raw_path.read_bytes()
        source_sha = sha256_bytes(raw_bytes)
        try:
            ast = parse_js(raw_bytes.decode("utf-8"))
            evidence = extract_evidence(ast, source_path=str(raw_path), source_sha256=source_sha)
            payload = evidence.to_dict()
            status = "ok"
            counts = {
                "ordered_calls": len(payload.get("ordered_calls", [])),
                "core_operator_chain": len(payload.get("core_operator_chain", [])),
                "io_contract": len(payload.get("io_contract", [])),
                "presentation_actions": len(payload.get("presentation_actions", [])),
                "support_calls": len(payload.get("support_calls", [])),
                "unresolved_calls": len(payload.get("unresolved_calls", [])),
                "quality_flags": len(payload.get("quality_flags", [])),
            }
            artifact_name = f"{script}_parser_evidence_v1.json"
            artifact = {"schema": "gee_six_script_parser_evidence_v1", "source_script": script, "source_path": str(raw_path), "source_sha256": source_sha, "extractor_version": EXTRACTOR_VERSION, "evidence": payload}
            (args.out_dir / artifact_name).write_text(json.dumps(artifact, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
            outputs[artifact_name] = sha256_file(args.out_dir / artifact_name)
        except Exception as exc:  # fail-closed per script
            status = f"fail_closed: {type(exc).__name__}: {exc}"
            counts = None
        per_script[script] = {"source_path": str(raw_path), "source_sha256": source_sha, "status": status, "layer_counts": counts}
    manifest = {
        "schema": "gee_six_script_parser_evidence_manifest_v1",
        "extractor_version": EXTRACTOR_VERSION,
        "scripts": per_script,
        "outputs": outputs,
        "policy": {
            "g0_modified": False,
            "training_admission": "not_granted",
            "production_samples": 0,
            "semantic_gold": False,
            "full_corpus_extraction": False,
        },
    }
    (args.out_dir / "parser_evidence_manifest_v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({script: item["status"] for script, item in per_script.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
