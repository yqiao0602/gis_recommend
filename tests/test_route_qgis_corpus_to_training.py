from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path


class RouteQgisCorpusTests(unittest.TestCase):
    def test_routes_source_joined_rows_and_never_emits_training(self) -> None:
        module = importlib.import_module("scripts.route_qgis_corpus_to_training")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "workflow.py"
            source.write_text(
                '''def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": fixed})["OUTPUT"]
''',
                encoding="utf-8",
            )
            row = {
                "record_id": "fixture",
                "source_path": str(source),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "call_sites": [
                    {"operator_id": "native:fixgeometries", "line_start": 2, "line_end": 2},
                    {"operator_id": "native:dissolve", "line_start": 3, "line_end": 3},
                ],
                "ordered_operator_ids": [
                    "native:fixgeometries",
                    "native:dissolve",
                ],
                "mapped_l3_chain": ["L3_A", "L3_B"],
                "api_pattern_calls": [],
                "call_graph_status": "single_scope",
            }
            input_path = root / "input.jsonl"
            input_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            routed, summary = module.route_corpus(input_path)
            self.assertEqual(summary["input_rows"], 1)
            self.assertEqual(summary["training_rows_emitted"], 0)
            self.assertEqual(summary["rule_counts"], {"direct-explicit-dag-v1": 1})
            self.assertEqual(
                summary["workflow_unit_scope_counts"],
                {"whole_processing_scope": 1},
            )
            self.assertEqual(
                summary["structure_class_counts"],
                {"valid_whole_processing_scope_candidate": 1},
            )
            self.assertEqual(
                summary["feature_extractor_versions"],
                ["qgis-conversion-features-v7"],
            )
            self.assertEqual(summary["task_text_rows_admitted"], 0)
            self.assertFalse(routed[0]["training_row_emitted"])
            self.assertEqual(routed[0]["action"], "auto_accept_candidate")
            self.assertEqual(
                routed[0]["ordered_operator_ids"],
                ["native:fixgeometries", "native:dissolve"],
            )
            self.assertEqual(
                routed[0]["dependency_edge_evidence"],
                [
                    {
                        "producer_index": 0,
                        "consumer_index": 1,
                        "kinds": ["variable_or_alias"],
                    }
                ],
            )

    def test_routes_static_path_dependency_evidence(self) -> None:
        module = importlib.import_module("scripts.route_qgis_corpus_to_training")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "static_path.py"
            source.write_text(
                '''def run(layer):
    processing.run("native:buffer", {"INPUT": layer, "OUTPUT": "buffered.gpkg"})
    return processing.run("native:fixgeometries", {"INPUT": "buffered.gpkg"})["OUTPUT"]
''',
                encoding="utf-8",
            )
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            row = {
                "record_id": "static-path",
                "source_path": str(source),
                "source_sha256": digest,
                "call_sites": [
                    {"operator_id": "native:buffer", "line_start": 2, "line_end": 2},
                    {"operator_id": "native:fixgeometries", "line_start": 3, "line_end": 3},
                ],
                "ordered_operator_ids": ["native:buffer", "native:fixgeometries"],
                "mapped_l3_chain": ["L3_A", "L3_B"],
                "api_pattern_calls": [],
                "call_graph_status": "single_scope",
            }
            path = root / "input.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")

            routed, _ = module.route_corpus(path)

            self.assertEqual(routed[0]["dependency_edges"], [[0, 1]])
            self.assertEqual(
                routed[0]["dependency_edge_evidence"],
                [
                    {
                        "producer_index": 0,
                        "consumer_index": 1,
                        "kinds": ["static_output_path"],
                    }
                ],
            )

    def test_source_drift_is_excluded(self) -> None:
        module = importlib.import_module("scripts.route_qgis_corpus_to_training")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "drift.py"
            source.write_text("processing.run('native:buffer', {})\n", encoding="utf-8")
            row = {
                "record_id": "drift",
                "source_path": str(source),
                "source_sha256": "wrong",
                "call_sites": [],
            }
            path = root / "input.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            routed, _ = module.route_corpus(path)
            self.assertEqual(routed[0]["rule_id"], "reject-source-drift-v1")
            self.assertEqual(routed[0]["action"], "exclude_current_chain")

    def test_joins_annotations_by_record_and_source_sha(self) -> None:
        module = importlib.import_module("scripts.route_qgis_corpus_to_training")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "api.py"
            source.write_text(
                'result = processing.run("native:buffer", {"INPUT": "x"})["OUTPUT"]\n',
                encoding="utf-8",
            )
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            row = {
                "record_id": "api",
                "source_path": str(source),
                "source_sha256": digest,
                "call_sites": [{"operator_id": "native:buffer", "line_start": 1, "line_end": 1}],
                "mapped_l3_chain": ["L3_A"],
            }
            annotation = {
                "record_id": "api",
                "source_sha256": digest,
                "api_pattern_calls": ["edit@2"],
                "call_graph_status": "single_scope",
            }
            input_path = root / "input.jsonl"
            annotations_path = root / "annotations.jsonl"
            input_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            annotations_path.write_text(json.dumps(annotation) + "\n", encoding="utf-8")
            routed, summary = module.route_corpus(input_path, annotations_path)
            self.assertEqual(summary["annotation_rows_joined"], 1)
            self.assertEqual(routed[0]["action"], "review_api_sidecar")


if __name__ == "__main__":
    unittest.main()
