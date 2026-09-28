from __future__ import annotations

import unittest

from scripts.build_qgis_api_wkt_geometry_train_only import (
    build_candidates,
    build_four_layer_dedup,
)


def _row(kind: str, identifier: str) -> dict:
    return {"macro_status": "complete", "wkt_geometry_rule_id": "qgis-api-wkt-geometry-local-macro-v1", "source_verification": "verified_sha256", "wkt_input_kind": kind, "evidence_snippet": "QgsGeometry.fromWkt(x)\nfeature.setGeometry(x)\nsink.addFeature(feature)", "source_span": [1, 3], "unit_id": identifier, "source_authority_key": f"body:{identifier}", "source_sha256": identifier * 64, "wkt_factory_line": 1, "setgeometry_line": 2, "sink_line": 3, "record_id": identifier, "source_path": f"/{identifier}.py"}


class BuildQgisApiWktGeometryTrainOnlyTest(unittest.TestCase):
    def test_builds_source_fact_descriptions_and_deduplicates_pairs(self) -> None:
        candidates = build_candidates([_row("variable_wkt", "a"), _row("variable_wkt", "b"), _row("literal_wkt", "c")])
        ledger, summary = build_four_layer_dedup(candidates)
        self.assertEqual(sum(row["description_fidelity_passed"] for row in candidates), 3)
        self.assertEqual(len(ledger), 3)
        self.assertEqual(summary["canonical_rows"], 2)


if __name__ == "__main__":
    unittest.main()
