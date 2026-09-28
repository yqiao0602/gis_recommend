"""Build the conservative human-review packet for GEE mean/clip templates.

The input is the combined authority representative ledger. Full source text is
used only to collapse near-duplicate authorities; no training row or human
approval is created.
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path, PurePosixPath
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _csv_text,
    _filesystem_path,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


BASE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "semantic_pattern_census_combined_11397_v1/authority_review_v1"
)
DEFAULT_INPUT = (
    BASE_DIR
    / "gee_semantic_authority_review_combined_11397_v1_representatives.jsonl"
)
DEFAULT_OUTPUT_DIR = BASE_DIR / "mean_clip_cluster_review_v1"
OUTPUT_PREFIX = "gee_mean_clip_cluster_review_35_v1"
DEFAULT_SOURCE_ROOTS = (
    ROOT / ".tmp_gee_semantic_census_3106_sources",
    ROOT / ".tmp_gee_semantic_remaining_8291_sources",
)


def _normalized_source(text: str) -> str:
    return " ".join(text.split())


def _similarity(left: str, right: str, threshold: float) -> float | None:
    matcher = SequenceMatcher(None, left, right)
    if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
        return None
    ratio = matcher.ratio()
    return ratio if ratio >= threshold else None


def build_cluster_review_packet(
    rows: list[dict[str, Any]],
    source_texts: dict[str, str],
    *,
    similarity_threshold: float = 0.8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = sorted(
        (row for row in rows if row.get("pattern") == "annual_mean_clip"),
        key=lambda row: str(row.get("source_sha256") or ""),
    )
    by_sha = {str(row.get("source_sha256") or ""): row for row in eligible}
    if "" in by_sha or len(by_sha) != len(eligible):
        raise ValueError("annual_mean_clip representatives require unique source SHA")
    missing = sorted(set(by_sha) - set(source_texts))
    if missing:
        raise ValueError(f"missing source text for {len(missing)} authorities")

    normalized = {key: _normalized_source(source_texts[key]) for key in by_sha}
    parent = {key: key for key in by_sha}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    pair_evidence: list[dict[str, Any]] = []
    source_shas = sorted(by_sha)
    for index, left_sha in enumerate(source_shas):
        for right_sha in source_shas[index + 1 :]:
            ratio = _similarity(
                normalized[left_sha],
                normalized[right_sha],
                similarity_threshold,
            )
            if ratio is None:
                continue
            union(left_sha, right_sha)
            pair_evidence.append(
                {
                    "left_source_sha256": left_sha,
                    "right_source_sha256": right_sha,
                    "similarity": round(ratio, 6),
                }
            )

    clusters: dict[str, list[str]] = {}
    for source_sha in source_shas:
        clusters.setdefault(find(source_sha), []).append(source_sha)

    packet: list[dict[str, Any]] = []
    for review_index, members in enumerate(sorted(clusters.values()), start=1):
        members = sorted(members)
        representative = by_sha[members[0]]
        member_set = set(members)
        edges = [
            edge
            for edge in pair_evidence
            if edge["left_source_sha256"] in member_set
            and edge["right_source_sha256"] in member_set
        ]
        cluster_id = "gee_mean_clip_" + sha256("|".join(members).encode()).hexdigest()[:16]
        packet.append(
            {
                "schema": "gis_recommend.gee_mean_clip_cluster_review.v1",
                "review_index": review_index,
                "cluster_id": cluster_id,
                "pattern": "annual_mean_clip",
                "cluster_member_count": len(members),
                "cluster_source_sha256s": members,
                "cluster_source_paths": [by_sha[key]["source_path"] for key in members],
                "cluster_sample_ids": [by_sha[key].get("sample_id") for key in members],
                "near_duplicate_evidence": edges,
                "representative_source_sha256": members[0],
                "representative_source_path": representative.get("source_path"),
                "representative_sample_id": representative.get("sample_id"),
                "representative_definition_id": representative.get("definition_id"),
                "canonical_operator_sequence": representative.get(
                    "canonical_operator_sequence", []
                ),
                "l3_code_sequence": representative.get("l3_code_sequence", []),
                "semantic_facts": representative.get("semantic_facts", {}),
                "source_snippet": representative.get("source_snippet", ""),
                "human_completeness": "",
                "human_fidelity": "",
                "human_adjudication": "",
                "human_notes": "",
                "training_admission": "not_granted_gee_mean_clip_cluster_review",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_mean_clip_cluster_review_summary.v1",
        "counts": {
            "input_representative_rows": len(rows),
            "eligible_authorities": len(eligible),
            "conservative_template_clusters": len(packet),
            "collapsed_authorities": len(eligible) - len(packet),
            "near_duplicate_pairs": len(pair_evidence),
            "human_reviewed_clusters": 0,
            "training_rows_emitted": 0,
        },
        "clustering": {
            "source_normalization": "collapse_all_whitespace_to_single_spaces",
            "similarity": "difflib.SequenceMatcher.ratio",
            "similarity_threshold": similarity_threshold,
            "linkage": "connected_components_of_pairs_at_or_above_threshold",
        },
        "gate": {
            "minimum_precision": 0.95,
            "minimum_wilson_95_lower": 0.8,
            "status": "not_evaluated_pending_human_review",
        },
        "decision": {
            "human_adjudication": "not_granted",
            "training_admission": "not_granted_gee_mean_clip_cluster_review",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "next_gate": "human completeness and fidelity review for every cluster",
        },
    }
    return packet, summary


def load_source_texts(
    rows: list[dict[str, Any]], source_roots: list[Path]
) -> dict[str, str]:
    texts: dict[str, str] = {}
    for row in rows:
        if row.get("pattern") != "annual_mean_clip":
            continue
        source_sha = str(row.get("source_sha256") or "")
        parts = PurePosixPath(str(row.get("source_path") or "")).parts
        if len(parts) < 2:
            raise ValueError(f"invalid source path for {source_sha}")
        relative_path = Path(*parts[-2:])
        matches = [root / relative_path for root in source_roots if (root / relative_path).is_file()]
        if not matches:
            raise FileNotFoundError(f"source not found for {row.get('source_path')}")
        source_file = matches[0]
        actual_sha = _sha256(source_file)
        if actual_sha != source_sha:
            raise ValueError(f"source SHA mismatch for {source_file}")
        with open(_filesystem_path(source_file), encoding="utf-8", errors="replace") as handle:
            texts[source_sha] = handle.read()
    return texts


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return "\n".join(
        [
            "# GEE Annual Mean/Clip 35-Cluster Human Review Packet v1",
            "",
            f"- Eligible source authorities: {counts['eligible_authorities']}",
            f"- Conservative template clusters: {counts['conservative_template_clusters']}",
            f"- Collapsed authorities: {counts['collapsed_authorities']}",
            f"- Near-duplicate pairs: {counts['near_duplicate_pairs']}",
            "- Human adjudication: not granted",
            "- Training rows emitted: 0",
            "",
            "Review every cluster for source-backed completeness and fidelity. "
            "Do not infer semantics from target-variable names.",
        ]
    ) + "\n"


def write_outputs(
    packet: list[dict[str, Any]],
    summary: dict[str, Any],
    input_path: Path,
    source_roots: list[Path],
    output_dir: Path,
) -> dict[str, Path]:
    paths = {
        "jsonl": output_dir / f"{OUTPUT_PREFIX}.jsonl",
        "csv": output_dir / f"{OUTPUT_PREFIX}.csv",
        "summary": output_dir / f"{OUTPUT_PREFIX}_summary.json",
        "report": output_dir / f"{OUTPUT_PREFIX}_report.md",
        "hash_ledger": output_dir / f"{OUTPUT_PREFIX}_hash_ledger.json",
    }
    summary = {
        **summary,
        "inputs": {
            "representatives_jsonl": str(input_path),
            "representatives_jsonl_sha256": _sha256(input_path),
            "source_roots": [str(path) for path in source_roots],
        },
    }
    _atomic_write(paths["jsonl"], _jsonl_text(packet))
    _atomic_write(paths["csv"], _csv_text(packet))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": summary["inputs"],
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--source-root", type=Path, action="append", dest="source_roots"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--similarity-threshold", type=float, default=0.8)
    args = parser.parse_args(argv)
    source_roots = args.source_roots or list(DEFAULT_SOURCE_ROOTS)
    rows = _load_jsonl(args.input_jsonl)
    source_texts = load_source_texts(rows, source_roots)
    packet, summary = build_cluster_review_packet(
        rows,
        source_texts,
        similarity_threshold=args.similarity_threshold,
    )
    return write_outputs(packet, summary, args.input_jsonl, source_roots, args.output_dir)


if __name__ == "__main__":
    main()
