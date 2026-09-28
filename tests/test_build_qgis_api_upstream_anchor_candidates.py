from __future__ import annotations

import unittest

from scripts.build_qgis_api_upstream_anchor_candidates import build_candidates


def _row(anchor: str, calls: list[str]) -> dict:
    return {
        "candidate_id": f"baseline-{anchor}",
        "record_id": "record",
        "source_path": "/source.py",
        "source_sha256": "a" * 64,
        "source_authority_key": "normalized_source_body_sha256:body",
        "normalized_source_body_sha256": "body",
        "source_root_id": "fixture",
        "relative_path": "source.py",
        "lexical_scope": "process",
        "slice_status": "resolved_local_call_chain",
        "source_verification": "verified_sha256",
        "semantic_anchor_families": [anchor],
        "upstream_calls": [
            {
                "call_name": call,
                "line_start": 10 + index,
                "line_end": 10 + index,
                "call_family": "geometry_method",
            }
            for index, call in enumerate(calls)
        ],
        "steps": [
            {
                "step_index": 0,
                "call_name": "output.setGeometry",
                "call_role": "feature_mutation",
                "line_start": 20,
                "line_end": 20,
                "receiver": "output",
                "terminal_evidence": False,
            },
            {
                "step_index": 1,
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


class BuildQgisApiUpstreamAnchorCandidatesTest(unittest.TestCase):
    def test_builds_unique_unary_union_local_candidate(self) -> None:
        candidates, sidecar, summary = build_candidates(
            [_row("unary_union", ["QgsGeometry.unaryUnion"])]
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(sidecar, [])
        self.assertEqual(candidates[0]["semantic_calls"], ["QgsGeometry.unaryUnion"])
        self.assertEqual(candidates[0]["dependency_edges"], [[0, 1], [1, 2]])
        self.assertEqual(summary["unary_union_candidate_units"], 1)
        self.assertEqual(summary["training_rows_emitted"], 0)

    def test_defers_random_point_anchor_for_missing_control_dependencies(self) -> None:
        candidates, sidecar, summary = build_candidates(
            [
                _row(
                    "random_point_construction",
                    ["random.random", "QgsGeometry.fromPointXY"],
                )
            ]
        )

        self.assertEqual(candidates, [])
        self.assertEqual(
            sidecar[0]["anchor_candidate_status"],
            "deferred_control_dependencies_outside_backward_slice",
        )
        self.assertEqual(summary["random_point_deferred_units"], 1)

    def test_fail_closes_non_unique_unary_union_call(self) -> None:
        candidates, sidecar, _ = build_candidates(
            [
                _row(
                    "unary_union",
                    ["QgsGeometry.unaryUnion", "QgsGeometry.unaryUnion"],
                )
            ]
        )

        self.assertEqual(candidates, [])
        self.assertEqual(
            sidecar[0]["anchor_candidate_status"],
            "deferred_non_unique_unary_union_call",
        )

    def test_fail_closes_transforms_after_unary_union(self) -> None:
        for downstream_call in (
            "QgsGeometry.polygonize",
            "geometry.asGeometryCollection",
        ):
            with self.subTest(downstream_call=downstream_call):
                candidates, sidecar, _ = build_candidates(
                    [
                        _row(
                            "unary_union",
                            ["QgsGeometry.unaryUnion", downstream_call],
                        )
                    ]
                )

                self.assertEqual(candidates, [])
                self.assertEqual(
                    sidecar[0]["anchor_candidate_status"],
                    "deferred_downstream_geometry_transform",
                )
                self.assertEqual(
                    sidecar[0]["downstream_geometry_transform_calls"],
                    [downstream_call],
                )


if __name__ == "__main__":
    unittest.main()
