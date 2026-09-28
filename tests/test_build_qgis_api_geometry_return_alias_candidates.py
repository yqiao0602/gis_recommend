from __future__ import annotations

import unittest

from scripts.build_qgis_api_geometry_return_alias_candidates import build_candidates


def _row(status: str, upstream_calls: list[dict]) -> dict:
    return {
        "candidate_id": "baseline",
        "record_id": "record",
        "source_path": "/source.py",
        "source_sha256": "a" * 64,
        "source_authority_key": "normalized_source_body_sha256:body",
        "normalized_source_body_sha256": "body",
        "source_root_id": "fixture",
        "relative_path": "source.py",
        "lexical_scope": "process",
        "mapping_status": "mutation_export_only",
        "slice_status": status,
        "source_verification": "verified_sha256",
        "upstream_calls": upstream_calls,
        "steps": [
            {
                "call_name": "output.setGeometry",
                "call_role": "feature_mutation",
                "line_start": 20,
                "line_end": 20,
                "receiver": "output",
                "terminal_evidence": False,
            },
            {
                "call_name": "sink.addFeature",
                "call_role": "sink_output",
                "line_start": 21,
                "line_end": 21,
                "receiver": "sink",
                "terminal_evidence": True,
            },
        ],
        "dependency_edges": [[0, 1]],
        "training_row_emitted": False,
    }


def _call(name: str, line: int, family: str = "geometry_method") -> dict:
    return {
        "call_name": name,
        "line_start": line,
        "line_end": line,
        "call_family": family,
    }


class BuildQgisApiGeometryReturnAliasCandidatesTest(unittest.TestCase):
    def test_builds_exact_alias_candidate_from_unique_backward_slice(self) -> None:
        rows = [
            _row(
                "resolved_local_call_chain",
                [_call("feature.geometry", 10, "geometry_accessor"), _call("geom.centroid", 11)],
            )
        ]

        candidates, ambiguous, summary = build_candidates(rows)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(ambiguous, [])
        self.assertEqual(candidates[0]["semantic_calls"], ["geom.centroid"])
        self.assertEqual(candidates[0]["dependency_edges"], [[0, 1], [1, 2]])
        self.assertEqual(candidates[0]["candidate_l3_sequence"], [])
        self.assertFalse(candidates[0]["training_row_emitted"])
        self.assertEqual(summary["resolved_candidate_units"], 1)

    def test_keeps_multiple_reaching_definitions_in_sidecar(self) -> None:
        rows = [
            _row(
                "ambiguous_multiple_reaching_definitions",
                [_call("geom.centroid", 11), _call("geom.centroid", 15)],
            )
        ]

        candidates, ambiguous, summary = build_candidates(rows)

        self.assertEqual(candidates, [])
        self.assertEqual(len(ambiguous), 1)
        self.assertEqual(ambiguous[0]["alias_candidate_status"], "deferred_ambiguous_reaching_definitions")
        self.assertEqual(summary["ambiguous_candidate_units"], 1)

    def test_fail_closes_resolved_slice_with_multiple_exact_methods(self) -> None:
        rows = [
            _row(
                "resolved_local_call_chain",
                [_call("geom.centroid", 11), _call("geom.convexHull", 12)],
            )
        ]

        candidates, ambiguous, _ = build_candidates(rows)

        self.assertEqual(candidates, [])
        self.assertEqual(ambiguous[0]["alias_candidate_status"], "deferred_non_unique_exact_method")

    def test_fail_closes_buffer_followed_by_geometry_difference(self) -> None:
        rows = [
            _row(
                "resolved_local_call_chain",
                [
                    _call("pt.buffer", 11),
                    _call("pt.buffer.difference", 11),
                ],
            )
        ]

        candidates, sidecar, summary = build_candidates(rows)

        self.assertEqual(candidates, [])
        self.assertEqual(
            sidecar[0]["alias_candidate_status"],
            "deferred_downstream_geometry_transform",
        )
        self.assertEqual(
            sidecar[0]["downstream_geometry_transform_calls"],
            ["pt.buffer.difference"],
        )
        self.assertEqual(summary["resolved_candidate_units"], 0)

    def test_fail_closes_buffer_reconstructed_after_union(self) -> None:
        rows = [
            _row(
                "resolved_local_call_chain",
                [
                    _call("QgsGeometry.fromPoint.buffer", 11),
                    _call("QgsGeometry.fromPoint.buffer.asWkb", 11),
                    _call("loads", 11, "external_or_custom"),
                    _call("QgsGeometry.fromWkt", 14, "qgsgeometry_factory"),
                    _call("cascaded_union", 14, "external_or_custom"),
                    _call("dumps", 14, "external_or_custom"),
                ],
            )
        ]

        candidates, sidecar, summary = build_candidates(rows)

        self.assertEqual(candidates, [])
        self.assertEqual(
            sidecar[0]["alias_candidate_status"],
            "deferred_downstream_geometry_transform",
        )
        self.assertEqual(
            sidecar[0]["downstream_geometry_transform_calls"],
            [
                "QgsGeometry.fromPoint.buffer.asWkb",
                "QgsGeometry.fromWkt",
                "cascaded_union",
            ],
        )
        self.assertEqual(summary["resolved_candidate_units"], 0)

    def test_ignores_factory_without_an_exact_geometry_method(self) -> None:
        rows = [
            _row(
                "resolved_local_call_chain",
                [_call("QgsGeometry.fromPointXY", 11, "qgsgeometry_factory")],
            )
        ]

        candidates, ambiguous, summary = build_candidates(rows)

        self.assertEqual(candidates, [])
        self.assertEqual(ambiguous, [])
        self.assertEqual(summary["broad_candidate_units"], 0)

    def test_excludes_previously_reviewed_baseline_candidates(self) -> None:
        rows = [
            _row(
                "resolved_local_call_chain",
                [_call("geom.centroid", 11)],
            )
        ]

        candidates, ambiguous, summary = build_candidates(
            rows, excluded_candidate_ids={"baseline"}
        )

        self.assertEqual(candidates, [])
        self.assertEqual(ambiguous, [])
        self.assertEqual(summary["excluded_previously_reviewed_units"], 1)


if __name__ == "__main__":
    unittest.main()
