import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.select_gee_workflow_dag_batch import freeze_authority_selection


class GeeWorkflowDagBatchSelectionTests(unittest.TestCase):
    def test_freezes_exact_source_disjoint_selection_without_parsing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "sources"
            source_root.mkdir()
            records = []
            for index, source in enumerate(
                (
                    "var x = ee.Image('A'); Export.image.toDrive({image: x});",
                    "var y = ee.Image('B'); Export.image.toDrive({image: y});",
                    "function f(x) { return x.clip(roi); }\n"
                    "var z = f(ee.Image('C')); Export.image.toDrive({image: z});",
                ),
                start=1,
            ):
                source = source + " " * max(0, 220 - len(source.encode("utf-8")))
                relative_path = f"data/script_{index}.js"
                source_path = source_root / relative_path
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_text(source, encoding="utf-8")
                source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
                records.append(
                    {
                        "record_key": relative_path,
                        "source_path": relative_path,
                        "source_sha256": source_hash,
                        "instances": [{"source_path": relative_path}],
                    }
                )
            records.sort(key=lambda row: row["source_sha256"])
            canonical = root / "canonical.jsonl"
            canonical.write_text(
                "".join(json.dumps(row) + "\n" for row in records),
                encoding="utf-8",
            )
            join = root / "join.jsonl"
            join.write_text(
                "".join(
                    json.dumps(
                        {
                            "join_status": "authoritative_exact_batch_join",
                            "source_path": row["source_path"],
                        }
                    )
                    + "\n"
                    for row in records
                ),
                encoding="utf-8",
            )
            excluded = root / "excluded.jsonl"
            excluded_row = {
                "record_key": records[0]["record_key"],
                "source_path": records[0]["source_path"],
                "source_sha256": records[0]["source_sha256"],
                "size_bytes": (source_root / records[0]["source_path"]).stat().st_size,
                "facts_supported": True,
                "calibration_stratum": "linear_export",
            }
            excluded.write_text(json.dumps(excluded_row) + "\n", encoding="utf-8")

            output = root / "output"
            summary = freeze_authority_selection(
                canonical_manifest=canonical,
                join_ledger=join,
                exclude_selection_manifest=excluded,
                source_root=source_root,
                output_dir=output,
                quotas={
                    "linear_export": 1,
                    "helper_export": 1,
                    "control_flow_export": 0,
                },
            )

            selected = [
                json.loads(line)
                for line in (output / "selection.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(summary["selected_source_count"], 2)
            self.assertEqual(summary["excluded_source_count"], 1)
            self.assertEqual(
                {row["calibration_stratum"] for row in selected},
                {"linear_export", "helper_export"},
            )
            self.assertNotIn(records[0]["source_sha256"], {
                row["source_sha256"] for row in selected
            })
            self.assertTrue((output / "hash_ledger.json").is_file())
            self.assertFalse((output / "ast").exists())


if __name__ == "__main__":
    unittest.main()
