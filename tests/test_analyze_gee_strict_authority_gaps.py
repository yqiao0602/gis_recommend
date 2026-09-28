from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp_test_analyze_gee_strict_authority_gaps"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeStrictAuthorityGapAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        TMP_ROOT.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_separates_receiver_resolution_clusters_from_l3_mapping_gaps(self) -> None:
        from scripts.analyze_gee_strict_authority_gaps import analyze_authority_gaps

        replay = TMP_ROOT / "replay.jsonl"
        _write_jsonl(
            replay,
            [
                {
                    "sample_id": "typed",
                    "unmapped_raw_operators": ["image.custom"],
                    "canonical_unmapped_l3_operators": ["ee.image.reducetovectors"],
                    "core_call_evidence": [
                        {
                            "raw_callee": "image.custom",
                            "receiver_type": "ee.image",
                            "resolution": "receiver_ee_binding",
                        }
                    ],
                },
                {
                    "sample_id": "proven_unknown",
                    "unmapped_raw_operators": ["value.get", "value.get"],
                    "canonical_unmapped_l3_operators": ["ee.image.reducetovectors"],
                    "core_call_evidence": [
                        {
                            "raw_callee": "value.get",
                            "receiver_type": None,
                            "resolution": "receiver_ee_binding",
                        }
                    ],
                },
                {
                    "sample_id": "untyped",
                    "unmapped_raw_operators": ["unknown.select"],
                    "canonical_unmapped_l3_operators": [],
                    "core_call_evidence": [
                        {
                            "raw_callee": "unknown.select",
                            "receiver_type": None,
                            "resolution": "receiver_untyped",
                        }
                    ],
                },
            ],
        )

        result = analyze_authority_gaps(replay_jsonl_path=replay)

        self.assertEqual(result.summary["counts"]["canonicalization_gap_rows"], 3)
        self.assertEqual(result.summary["counts"]["unmapped_raw_occurrences"], 4)
        self.assertEqual(
            result.summary["canonicalization_category_counts"],
            {
                "proven_ee_type_unresolved": 2,
                "typed_receiver_operator_gap": 1,
                "untyped_receiver": 1,
            },
        )
        self.assertEqual(result.summary["counts"]["l3_mapping_gap_rows"], 2)
        self.assertEqual(result.l3_operator_clusters[0]["operator"], "ee.image.reducetovectors")
        self.assertEqual(result.l3_operator_clusters[0]["occurrences"], 2)
        self.assertEqual(result.summary["decision"]["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
