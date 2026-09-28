from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
    / "strict_candidate_v1"
)
CANDIDATE_JSON = PACKAGE_DIR / "gee_strict_candidate_v1_train3106.json"
TMP_ROOT = ROOT / ".tmp_test_gee_strict_candidate_source_audit"


def _ident(name: str) -> dict:
    return {"type": "Identifier", "name": name}


def _member(obj: dict, prop: str) -> dict:
    return {
        "type": "MemberExpression",
        "computed": False,
        "object": obj,
        "property": _ident(prop),
    }


def _call(callee: dict, *arguments: dict) -> dict:
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def _var(name: str, init: dict) -> dict:
    return {
        "type": "VariableDeclaration",
        "declarations": [{"type": "VariableDeclarator", "id": _ident(name), "init": init}],
    }


def _program(*statements: dict) -> dict:
    return {"type": "Program", "body": list(statements)}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeStrictCandidateSourceAuditTests(unittest.TestCase):
    def test_direct_cli_can_generate_sample_package(self) -> None:
        audit = importlib.import_module("scripts.build_gee_strict_candidate_source_audit")
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        output_dir = TMP_ROOT / "cli_sample"
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_gee_strict_candidate_source_audit.py"),
                    "--phase",
                    "sample",
                    "--candidate-json",
                    str(CANDIDATE_JSON),
                    "--sample-size",
                    "60",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(
                (output_dir / "strict_candidate_audit_sample_60_v1.jsonl").is_file()
            )
        finally:
            shutil.rmtree(audit._filesystem_path(TMP_ROOT), ignore_errors=True)

    def test_selects_reproducible_60_rows_covering_all_candidate_task_types(self) -> None:
        audit = importlib.import_module("scripts.build_gee_strict_candidate_source_audit")

        first = audit.build_stratified_sample(
            candidate_json=CANDIDATE_JSON,
            sample_size=60,
            seed="gee_strict_candidate_source_audit_v1",
        )
        second = audit.build_stratified_sample(
            candidate_json=CANDIDATE_JSON,
            sample_size=60,
            seed="gee_strict_candidate_source_audit_v1",
        )
        candidate_rows = json.loads(CANDIDATE_JSON.read_text(encoding="utf-8"))[
            "labeled_workflows"
        ]

        self.assertEqual(len(first.rows), 60)
        self.assertEqual(
            [row["sample_id"] for row in first.rows],
            [row["sample_id"] for row in second.rows],
        )
        self.assertEqual(len({row["sample_id"] for row in first.rows}), 60)
        self.assertEqual(len({row["source_sha256"] for row in first.rows}), 60)
        self.assertEqual(
            {row["task_type"] for row in first.rows},
            {row["task_type"] for row in candidate_rows},
        )
        self.assertEqual(first.summary["counts"]["candidate_rows"], 3106)
        self.assertEqual(first.summary["counts"]["sample_rows"], 60)
        self.assertEqual(first.summary["counts"]["covered_task_types"], 41)
        self.assertEqual(first.summary["decision"]["training_rows_emitted"], 0)
        self.assertFalse(first.summary["decision"]["validation_eligible"])
        self.assertFalse(first.summary["decision"]["test_eligible"])
        for row in first.rows:
            self.assertEqual(row["training_admission"], "not_granted_source_audit_calibration")
            self.assertEqual(row["frozen_operator_sequence"], row["operator_sequence"])
            self.assertEqual(row["frozen_l3_code_sequence"], row["l3_code_sequence"])
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])

    def test_source_replay_is_hash_bound_and_changed_chains_remain_fail_closed(self) -> None:
        audit = importlib.import_module("scripts.build_gee_strict_candidate_source_audit")
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        source_dir = TMP_ROOT / "sources"
        ast_dir = TMP_ROOT / "ast"
        source_dir.mkdir(parents=True)
        ast_dir.mkdir(parents=True)

        try:
            ast = _program(
                _var("image", _call(_member(_ident("ee"), "Image"))),
                _var(
                    "ndvi",
                    _call(_member(_ident("image"), "normalizedDifference")),
                )
            )
            sample_rows = []
            for name, frozen_sequence, frozen_l3 in (
                ("exact", ["ee.image.normalizeddifference"], ["L3_03_08_01"]),
                ("changed", ["ee.image.clip"], ["L3_03_01_04"]),
            ):
                source = source_dir / f"{name}.txt"
                source.write_text(
                    f"var image = ee.Image(1); var {name} = image.normalizedDifference();",
                    encoding="utf-8",
                )
                source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
                source.rename(source_dir / f"{source_hash}.txt")
                (ast_dir / f"{source_hash}.ast.json").write_text(
                    json.dumps(ast), encoding="utf-8"
                )
                sample_rows.append(
                    {
                        "sample_id": f"sample_{name}",
                        "source_sha256": source_hash,
                        "source_path": f"/home/yll/GEE/Data/{name}.txt",
                        "task_type": "Vegetation",
                        "task_name": name,
                        "task_description": name,
                        "frozen_operator_sequence": frozen_sequence,
                        "frozen_l3_code_sequence": frozen_l3,
                    }
                )
            sample_rows.append(
                {
                    "sample_id": "sample_missing",
                    "source_sha256": "f" * 64,
                    "source_path": "/home/yll/GEE/Data/missing.txt",
                    "task_type": "Vegetation",
                    "task_name": "missing",
                    "task_description": "missing",
                    "frozen_operator_sequence": ["ee.image.clip"],
                    "frozen_l3_code_sequence": ["L3_03_01_04"],
                }
            )
            sample_path = TMP_ROOT / "sample.jsonl"
            _write_jsonl(sample_path, sample_rows)

            result = audit.build_source_replay(
                sample_jsonl=sample_path,
                source_dir=source_dir,
                ast_dir=ast_dir,
            )

            by_id = {row["sample_id"]: row for row in result.rows}
            self.assertEqual(by_id["sample_exact"]["sequence_relationship"], "exact")
            self.assertEqual(
                by_id["sample_exact"]["raw_replayed_core_operator_sequence"],
                ["image.normalizeddifference"],
            )
            self.assertEqual(
                by_id["sample_exact"]["replayed_core_operator_sequence"],
                ["ee.image.normalizeddifference"],
            )
            self.assertEqual(
                by_id["sample_exact"]["alignment_window_call_evidence"][0]["receiver_type"],
                "ee.image",
            )
            self.assertEqual(by_id["sample_exact"]["unmapped_raw_operators"], [])
            self.assertEqual(
                by_id["sample_exact"]["canonical_unmapped_l3_operators"], []
            )
            self.assertTrue(by_id["sample_exact"]["l3_sequence_match"])
            self.assertEqual(
                by_id["sample_exact"]["replay_disposition"],
                "exact_replay_pending_human_fidelity_review",
            )
            self.assertEqual(
                by_id["sample_exact"]["frozen_alignment_status"],
                "complete_minimal_window",
            )
            self.assertEqual(by_id["sample_exact"]["frozen_alignment_coverage"], 1.0)
            self.assertEqual(by_id["sample_exact"]["alignment_window_extra_operators"], [])
            self.assertEqual(
                by_id["sample_exact"]["alignment_window_call_evidence"][0][
                    "canonical_operator"
                ],
                "ee.image.normalizeddifference",
            )
            self.assertEqual(
                by_id["sample_exact"]["alignment_window_call_evidence"][0][
                    "ordered_call_ordinal"
                ],
                1,
            )
            self.assertEqual(
                by_id["sample_exact"]["alignment_review_status"],
                "exact_window_pending_human_fidelity_review",
            )
            self.assertEqual(by_id["sample_changed"]["sequence_relationship"], "changed")
            self.assertEqual(
                by_id["sample_changed"]["replay_disposition"],
                "fail_closed_chain_difference",
            )
            self.assertEqual(by_id["sample_missing"]["reextract_status"], "source_missing")
            self.assertEqual(
                by_id["sample_missing"]["replay_disposition"], "fail_closed_input_error"
            )
            self.assertEqual(result.summary["counts"]["source_hash_verified_rows"], 2)
            self.assertEqual(result.summary["counts"]["exact_replay_rows"], 1)
            self.assertEqual(result.summary["counts"]["l3_mapping_gap_rows"], 0)
            self.assertEqual(result.summary["counts"]["complete_alignment_rows"], 1)
            self.assertEqual(result.summary["counts"]["exact_alignment_window_rows"], 1)
            self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
            for row in result.rows:
                self.assertEqual(row["training_admission"], "not_granted_source_audit_calibration")
                self.assertEqual(row["human_chain_verdict"], "")
                self.assertEqual(row["human_task_text_verdict"], "")
                self.assertFalse(row["validation_eligible"])
                self.assertFalse(row["test_eligible"])

            outputs = audit.write_replay_outputs(
                result,
                output_dir=TMP_ROOT / "replay_outputs",
                sample_jsonl=sample_path,
            )
            self.assertTrue(outputs["alignment_review_jsonl"].is_file())
            self.assertTrue(outputs["alignment_review_csv"].is_file())
            alignment_rows = [
                json.loads(line)
                for line in outputs["alignment_review_jsonl"].read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(alignment_rows), 1)
            self.assertEqual(
                alignment_rows[0]["regenerated_operator_sequence"],
                ["ee.image.normalizeddifference"],
            )
            self.assertEqual(alignment_rows[0]["human_final_decision"], "")
            self.assertEqual(
                alignment_rows[0]["training_admission"],
                "not_granted_source_audit_calibration",
            )
            ledger = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
            report = outputs["report"].read_text(encoding="utf-8")
            self.assertIn("Complete frozen-chain alignment: 1", report)
            self.assertIn("Exact minimal alignment window: 1", report)
            self.assertIn("Alignment review candidates: 1", report)
            self.assertEqual(len(ledger["source_inputs"]["verified_source_files"]), 2)
            self.assertEqual(len(ledger["source_inputs"]["verified_ast_files"]), 2)
            self.assertIn("id_mappings_v2.json", ledger["source_inputs"])

            no_candidate_outputs = audit.write_replay_outputs(
                audit.SourceReplayResult(
                    rows=[by_id["sample_changed"]],
                    summary=result.summary,
                ),
                output_dir=TMP_ROOT / "no_alignment_candidate_outputs",
                sample_jsonl=sample_path,
            )
            self.assertNotIn("alignment_review_jsonl", no_candidate_outputs)
            self.assertNotIn("alignment_review_csv", no_candidate_outputs)
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_fatal_quality_flags_block_exact_replay(self) -> None:
        audit = importlib.import_module("scripts.build_gee_strict_candidate_source_audit")

        relationship, disposition = audit.classify_replay(
            ["ee.image.select"],
            ["ee.image.select"],
            ["dynamic_callee"],
        )

        self.assertEqual(relationship, "exact")
        self.assertEqual(disposition, "fail_closed_extractor_quality")

        _, external_disposition = audit.classify_replay(
            ["ee.image.select"],
            ["ee.image.select"],
            ["external_module_call"],
        )
        self.assertEqual(external_disposition, "fail_closed_extractor_quality")

    def test_alignment_uses_narrowest_complete_source_window(self) -> None:
        audit = importlib.import_module("scripts.build_gee_strict_candidate_source_audit")

        alignment = audit.align_frozen_sequence(
            ["a", "b"],
            ["a", "x", "b", "a", "b", "tail"],
        )

        self.assertEqual(alignment.status, "complete_minimal_window")
        self.assertEqual(alignment.matched_replay_indices, [3, 4])
        self.assertEqual(alignment.window_replay_indices, [3, 4])
        self.assertEqual(alignment.extra_replay_indices, [])
        self.assertEqual(alignment.frozen_coverage, 1.0)

    def test_alignment_reports_partial_ordered_coverage_without_claiming_complete(self) -> None:
        audit = importlib.import_module("scripts.build_gee_strict_candidate_source_audit")

        alignment = audit.align_frozen_sequence(
            ["a", "b", "c"],
            ["a", "x", "c"],
        )

        self.assertEqual(alignment.status, "partial_lcs")
        self.assertEqual(alignment.matched_frozen_indices, [0, 2])
        self.assertEqual(alignment.matched_replay_indices, [0, 2])
        self.assertEqual(alignment.frozen_coverage, 2 / 3)


if __name__ == "__main__":
    unittest.main()
