import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_gee_extractor_pilot_manifest.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_gee_extractor_pilot_manifest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BuildGeeExtractorPilotManifestTests(unittest.TestCase):
    def test_source_features_distinguish_callback_helper_control_and_presentation(self):
        module = _load_module()
        source = """
        function helper(image) { return image.clip(region); }
        var a = collection.map(function(image) { return helper(image); });
        var b = collection.map(image => image.addBands(mask));
        if (ready) { Export.image.toDrive({image: b}); Map.addLayer(b); }
        """

        self.assertEqual(module.classify_source_features(source), {
            "arrow_callback",
            "branch_loop",
            "function_callback",
            "helper",
            "io_presentation",
        })

    def test_selection_is_hash_disjoint_deterministic_and_keeps_required_record(self):
        module = _load_module()
        records = [
            {"record_id": "z", "source_sha256": "1" * 64, "source_text": "var x = image.clip(a);"},
            {"record_id": "mirror", "source_sha256": "1" * 64, "source_text": "var x = image.clip(a);"},
            {"record_id": "arrow", "source_sha256": "2" * 64, "source_text": "c.map(x => x.clip(a));"},
            {"record_id": "required", "source_sha256": "3" * 64, "source_text": "print(image);"},
        ]

        first = module.select_candidates(
            records,
            quotas={"arrow_callback": 1, "direct_chain": 1},
            required_record_ids={"required"},
        )
        second = module.select_candidates(
            list(reversed(records)),
            quotas={"arrow_callback": 1, "direct_chain": 1},
            required_record_ids={"required"},
        )

        self.assertEqual([row["record_id"] for row in first], [row["record_id"] for row in second])
        self.assertEqual(len({row["source_sha256"] for row in first}), len(first))
        self.assertIn("required", [row["record_id"] for row in first])
        self.assertEqual(len(first), 3)

    def test_replay_manifest_hash_mismatch_fails_closed(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "script_1.txt"
            source.write_text("var image = ee.Image(1);", encoding="utf-8")
            manifest = root / "batch.jsonl"
            manifest.write_text(json.dumps({
                "script_name": source.name,
                "source_path": str(source),
                "source_sha256": "f" * 64,
                "status": "processed",
                "steps_path": str(root / "steps.csv"),
            }) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "source_sha256 mismatch"):
                module._load_replay_records(root)


if __name__ == "__main__":
    unittest.main()
