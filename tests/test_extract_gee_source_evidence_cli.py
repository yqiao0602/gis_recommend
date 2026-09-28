import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_gee_source_evidence.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("extract_gee_source_evidence_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExtractGeeSourceEvidenceCliTests(unittest.TestCase):
    def test_build_evidence_manifest_binds_source_ast_and_relative_evidence_path(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "script.txt"
            source.write_text("var image = ee.Image(1);", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            ast = root / "script_ast.json"
            ast.write_text(json.dumps({
                "type": "Program",
                "body": [{
                    "type": "ExpressionStatement",
                    "expression": {
                        "type": "CallExpression",
                        "callee": {
                            "type": "MemberExpression",
                            "computed": False,
                            "object": {"type": "Identifier", "name": "ee"},
                            "property": {"type": "Identifier", "name": "Image"},
                        },
                        "arguments": [{"type": "Literal", "value": 1}],
                    },
                }],
            }), encoding="utf-8")
            output = root / "output"

            summary = module.build_evidence_manifest([{
                "record_id": "record-1",
                "source_path": str(source),
                "source_sha256": source_hash,
                "ast_path": str(ast),
                "legacy_operations": ["ee.Image"],
                "pilot_feature": "required_regression",
                "source_features": ["helper"],
            }], output)

            self.assertEqual(summary["record_count"], 1)
            manifest_record = json.loads((output / "manifest.jsonl").read_text(encoding="utf-8"))
            self.assertTrue(manifest_record["evidence_path"].startswith("evidence/"))
            self.assertEqual(manifest_record["pilot_feature"], "required_regression")
            self.assertEqual(manifest_record["source_features"], ["helper"])
            evidence = json.loads((output / manifest_record["evidence_path"]).read_text(encoding="utf-8"))
            self.assertEqual(evidence["source_sha256"], source_hash)
            self.assertEqual(evidence["support_calls"], [0])
            self.assertEqual(summary["extractor_version"], evidence["extractor_version"])

    def test_build_evidence_manifest_rejects_hash_mismatch_and_duplicate_ids(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "script.txt"
            source.write_text("var image = ee.Image(1);", encoding="utf-8")
            ast = root / "script_ast.json"
            ast.write_text(json.dumps({"type": "Program", "body": []}), encoding="utf-8")
            record = {
                "record_id": "same",
                "source_path": str(source),
                "source_sha256": "f" * 64,
                "ast_path": str(ast),
            }

            with self.assertRaisesRegex(ValueError, "source_sha256 mismatch"):
                module.build_evidence_manifest([record], root / "bad-hash")

            record["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "duplicate record_id"):
                module.build_evidence_manifest([record, dict(record)], root / "duplicate")


if __name__ == "__main__":
    unittest.main()
