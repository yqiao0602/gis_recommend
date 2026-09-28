from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_second_source_review_50_v1"
)
REVIEW_JSONL = REVIEW_DIR / "stable101_source_review_50_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_qgis_second_salvage_preclass"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _workspace(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _review_row(
    source_path: Path,
    *,
    review_index: int,
    operators: list[str],
) -> dict[str, object]:
    lines = source_path.read_text(encoding="utf-8").splitlines()
    sites: list[dict[str, object]] = []
    cursor = 0
    for ordinal, operator_id in enumerate(operators, start=1):
        for line_index in range(cursor, len(lines)):
            if operator_id in lines[line_index]:
                sites.append(
                    {
                        "ordinal": ordinal,
                        "operator_id": operator_id,
                        "line_start": line_index + 1,
                        "line_end": line_index + 1,
                    }
                )
                cursor = line_index + 1
                break
        else:
            raise AssertionError(f"operator not found in fixture: {operator_id}")
    return {
        "review_index": review_index,
        "record_id": f"fixture-{review_index}",
        "source_root_id": "fixture",
        "source_path": str(source_path),
        "relative_path": source_path.name,
        "source_sha256": _sha256(source_path),
        "joined_source_status": "joined_and_chain_verified",
        "source_snippet_contains_all_ops": True,
        "ordered_operator_ids": operators,
        "mapped_l3_chain": ["L3_fixture"] * len(operators),
        "call_sites": sites,
        "task_text": "fixture task",
        "task_text_quality": "usable_seed_text",
        "human_workflow_boundary_decision": "",
        "human_operator_identity_order_decision": "",
        "human_dependency_decision": "",
        "human_task_text_usable": "",
        "human_training_candidate_ready": "",
        "human_description_generation_ready": "",
        "human_source_retrieval_ready": "",
        "human_notes": "",
        "training_admission": "not_granted",
    }


class QgisSecondSalvagePreclassificationTests(unittest.TestCase):
    def test_classifies_synthetic_source_structures_without_review_indices(self) -> None:
        preclass = importlib.import_module(
            "scripts.build_qgis_stable101_second_salvage_preclassification"
        )
        workspace = _workspace("structures")
        fixtures = {
            "ready_now.py": '''def run():
    layer = processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]
    return processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
''',
            "call_graph.py": '''def load_step():
    return processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]

def finish_step(layer):
    return processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]

def run():
    return finish_step(load_step())
''',
            "split.py": '''def example_one():
    return processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]

def example_two():
    return processing.run("native:fixgeometries", {"INPUT": "y"})["OUTPUT"]
''',
            "api_pattern.py": '''def run():
    layer = processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]
    for feature in layer.getFeatures():
        feature.setGeometry(feature.geometry().buffer(1, 4))
    return processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
''',
            "branch.py": '''def run(enabled):
    layer = processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]
    if enabled:
        layer = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return layer
''',
            "comment_only.py": '''def run():
    """processing.run("native:buffer", {"INPUT": "x"})"""
    return processing.run("native:fixgeometries", {"INPUT": "x"})["OUTPUT"]
''',
            "bound_processing.py": '''def run(self):
    layer = self.processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]
    return self.processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
''',
            "dynamic_extra.py": '''def run(algorithm_id):
    layer = processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]
    layer = processing.run(algorithm_id, {"INPUT": layer})["OUTPUT"]
    return processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
''',
        }
        rows: list[dict[str, object]] = []
        operators = ["native:buffer", "native:fixgeometries"]
        for index, (name, source) in enumerate(fixtures.items(), start=1):
            source_path = workspace / name
            source_path.write_text(source, encoding="utf-8")
            rows.append(
                _review_row(
                    source_path,
                    review_index=index,
                    operators=operators,
                )
            )
        review_jsonl = workspace / "review.jsonl"
        review_jsonl.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

        result = preclass.build_preclassification(
            review_jsonl_path=review_jsonl,
            expected_row_count=8,
        )

        by_name = {Path(row["source_path"]).name: row for row in result.rows}
        self.assertEqual(by_name["ready_now.py"]["salvage_class"], "ready_now")
        self.assertEqual(
            by_name["call_graph.py"]["salvage_class"],
            "recoverable_call_graph",
        )
        self.assertEqual(
            by_name["split.py"]["salvage_class"], "split_subworkflow"
        )
        self.assertEqual(
            by_name["api_pattern.py"]["salvage_class"],
            "api_pattern_deferred",
        )
        self.assertEqual(
            by_name["branch.py"]["salvage_class"],
            "recoverable_call_graph",
        )
        self.assertEqual(by_name["comment_only.py"]["salvage_class"], "exclude")
        self.assertEqual(
            by_name["bound_processing.py"]["salvage_class"], "ready_now"
        )
        self.assertEqual(
            by_name["dynamic_extra.py"]["salvage_class"],
            "recoverable_call_graph",
        )
        for row in result.rows:
            self.assertEqual(row["classification_status"], "preclassification_only")
            self.assertTrue(row["human_confirmation_required"])
            self.assertEqual(row["training_admission"], "not_granted")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_real_second_batch_preserves_provenance_and_human_fields(self) -> None:
        preclass = importlib.import_module(
            "scripts.build_qgis_stable101_second_salvage_preclassification"
        )
        result = preclass.build_preclassification(review_jsonl_path=REVIEW_JSONL)

        self.assertEqual(result.report["counts"]["rows"], 50)
        self.assertEqual(
            set(result.report["salvage_classes"]),
            {
                "ready_now",
                "recoverable_call_graph",
                "split_subworkflow",
                "api_pattern_deferred",
                "exclude",
            },
        )
        original_rows = {
            int(row["review_index"]): row
            for row in (
                json.loads(line)
                for line in REVIEW_JSONL.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        by_index = {int(row["review_index"]): row for row in result.rows}
        for index, row in by_index.items():
            original = original_rows[index]
            self.assertEqual(row["source_sha256"], original["source_sha256"])
            self.assertEqual(row["record_id"], original["record_id"])
            self.assertEqual(row["ordered_operator_ids"], original["ordered_operator_ids"])
            for field, value in original.items():
                if field.startswith("human_"):
                    self.assertEqual(value, "")
                    self.assertEqual(row[field], "")
        for contaminated_index in (7, 9, 14, 36, 46):
            self.assertEqual(by_index[contaminated_index]["salvage_class"], "exclude")
        self.assertEqual(
            result.report["decision"]["training_admission"], "not_granted"
        )
        self.assertTrue(result.report["decision"]["human_confirmation_required"])

    def test_cli_writes_five_artifacts_without_modifying_review_pack(self) -> None:
        preclass = importlib.import_module(
            "scripts.build_qgis_stable101_second_salvage_preclassification"
        )
        output_dir = _workspace("cli")
        before = REVIEW_JSONL.read_bytes()
        try:
            outputs = preclass.main(
                [
                    "--review-jsonl",
                    str(REVIEW_JSONL),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            self.assertEqual(
                set(outputs), {"csv", "jsonl", "summary", "report", "hash_ledger"}
            )
            for path in outputs.values():
                self.assertTrue(path.exists(), path)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 50)
            self.assertEqual(len(outputs["jsonl"].read_text(encoding="utf-8").splitlines()), 50)
            summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            self.assertEqual(
                summary["schema"],
                "gis_recommend.qgis_stable101_second_salvage_preclassification.v1",
            )
        finally:
            self.assertEqual(REVIEW_JSONL.read_bytes(), before)
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
