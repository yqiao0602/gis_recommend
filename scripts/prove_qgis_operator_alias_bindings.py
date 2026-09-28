#!/usr/bin/env python3
"""Prove exact ``qgis:<slug>`` to ``native:<slug>`` aliases for operator evidence rows.

The qualification layer may only map a ``qgis:`` operator through the
``native:`` mapping authority when every backing source row independently proves
the same-slug migration. This prover re-reads each source file, re-verifies its
SHA, and re-locates the exact literal Processing call recorded by the evidence
sidecar - across ``processing.run``, ``processing.runalg``,
``processing.runAndLoadResults``, and their imported bare-name forms - before
recording a migration. It emits proof records only; no L3 label, training row,
or authority change is produced here.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_operator_alias_proof.v1"
RULE = "qgis_to_native_same_slug"
ENTRYPOINTS = frozenset({"run", "runalg", "runAndLoadResults"})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _literal_calls(source: str) -> dict[tuple[int, int], tuple[str, str]]:
    """Map ``(lineno, col_offset)`` to ``(entrypoint, literal operator id)``."""
    calls: dict[tuple[int, int], tuple[str, str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr in ENTRYPOINTS and isinstance(function.value, ast.Name) and function.value.id == "processing":
            entrypoint = function.attr
        elif isinstance(function, ast.Name) and function.id in ENTRYPOINTS:
            entrypoint = function.id
        else:
            continue
        calls[(node.lineno, node.col_offset)] = (entrypoint, first.value.strip().lower())
    return calls


def prove(
    sidecar_rows: list[dict[str, Any]],
    mapping: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    proofs: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    candidate_rows = 0
    for row in sidecar_rows:
        if row.get("status") != "source_verified_ast":
            continue
        for call in row.get("calls") or []:
            operator_id = str(call.get("operator_id") or "")
            provider, _, slug = operator_id.partition(":")
            if provider != "qgis":
                continue
            canonical = f"native:{slug}"
            if canonical not in mapping:
                continue
            candidate_rows += 1
            record_id = str(row.get("record_id") or "")
            path = Path(str(row.get("source_path") or ""))
            span = call.get("source_span") or {}
            base = {
                "schema": SCHEMA,
                "record_id": record_id,
                "source_path": str(path),
                "source_sha256": row.get("source_sha256"),
                "source_operator": operator_id,
                "canonical_operator": canonical,
                "rule": RULE,
                "l3_via_canonical": mapping[canonical],
                "sidecar_entrypoint": call.get("entrypoint"),
                "source_expression": call.get("source_expression"),
                "source_span": span,
            }
            if not path.is_file():
                failures.append({"record_id": record_id, "operator_id": operator_id, "reason": "source_unavailable"})
                continue
            if _sha256(path) != str(row.get("source_sha256") or ""):
                failures.append({"record_id": record_id, "operator_id": operator_id, "reason": "source_sha256_mismatch"})
                continue
            try:
                calls = _literal_calls(path.read_text(encoding="utf-8-sig"))
            except (SyntaxError, UnicodeError) as exc:
                failures.append({"record_id": record_id, "operator_id": operator_id, "reason": f"source_parse_error:{type(exc).__name__}"})
                continue
            located = calls.get((int(span.get("line_start") or 0), int(span.get("column_start") or 0)))
            if located is None:
                failures.append({"record_id": record_id, "operator_id": operator_id, "reason": "call_not_found_at_recorded_span"})
                continue
            entrypoint, literal = located
            if literal != operator_id:
                failures.append({"record_id": record_id, "operator_id": operator_id, "reason": f"literal_operator_mismatch:{literal}"})
                continue
            if entrypoint != str(call.get("entrypoint") or ""):
                failures.append({"record_id": record_id, "operator_id": operator_id, "reason": f"entrypoint_mismatch:{entrypoint}"})
                continue
            proofs.append({**base, "entrypoint": entrypoint, "literal_operator": literal, "status": "verified_exact_same_slug"})

    run_attribute = [proof for proof in proofs if str(proof.get("source_expression") or "").startswith("processing.run(")]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "sidecar_rows": len(sidecar_rows),
        "candidate_rows": candidate_rows,
        "verified_rows": len(proofs),
        "failed_rows": len(failures),
        "verified_by_entrypoint": dict(sorted(Counter(proof["entrypoint"] for proof in proofs).items())),
        "verified_by_operator": dict(sorted(Counter(proof["source_operator"] for proof in proofs).items())),
        "failure_reasons": dict(sorted(Counter(reason.split(":")[0] for _, _, reason in ((f["record_id"], f.get("operator_id"), f["reason"]) for f in failures)).items())),
        "precedent_crosscheck_subset": {
            "processing_run_attribute_form": len(run_attribute),
            "note": "subset visible to scripts/verify_qgis_processing_provider_aliases.py",
        },
        "rule": RULE,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_alias_proof_only",
        "formal_authority_modified": False,
    }
    return proofs, failures, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    proofs, failures, summary = prove(read_jsonl(args.sidecar), mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    proof_path = args.output_dir / "alias_proof_v1.jsonl"
    failure_path = args.output_dir / "alias_proof_failures_v1.jsonl"
    summary_path = args.output_dir / "alias_proof_summary_v1.json"
    proof_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in proofs), encoding="utf-8")
    failure_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in failures), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (proof_path, failure_path, summary_path)}
    hashes["sidecar_input"] = _sha256(args.sidecar)
    hashes["mapping_input"] = _sha256(args.mapping)
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
