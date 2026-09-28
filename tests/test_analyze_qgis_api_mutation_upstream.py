from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_qgis_api_mutation_upstream import (
    analyze_candidate_path,
    analyze_candidate_source,
    build_census,
)


def _candidate(set_geometry_line: int, source_sha256: str = "") -> dict:
    return {
        "candidate_id": "candidate-1",
        "mapping_status": "mutation_export_only",
        "normalized_source_body_sha256": "body-1",
        "source_authority_key": "normalized_source_body_sha256:body-1",
        "source_path": "/source.py",
        "source_sha256": source_sha256,
        "steps": [
            {
                "call_name": "output.setGeometry",
                "call_role": "feature_mutation",
                "line_start": set_geometry_line,
                "line_end": set_geometry_line,
                "receiver": "output",
                "consumed_names": ["output", "geometry"],
            },
            {
                "call_name": "sink.addFeature",
                "call_role": "sink_output",
                "line_start": set_geometry_line + 1,
                "line_end": set_geometry_line + 1,
                "receiver": "sink",
                "consumed_names": ["output", "sink"],
            },
        ],
    }


def _terminal_only_candidate(sink_line: int, source_sha256: str = "") -> dict:
    candidate = _candidate(sink_line - 1, source_sha256)
    candidate["steps"] = [
        {
            "call_name": "output.setAttributes",
            "call_role": "attribute_mutation",
            "line_start": sink_line - 1,
            "line_end": sink_line - 1,
        },
        {
            "call_name": "sink.addFeature",
            "call_role": "sink_output",
            "line_start": sink_line,
            "line_end": sink_line,
        },
    ]
    return candidate


class AnalyzeQgisApiMutationUpstreamTest(unittest.TestCase):
    def test_recovers_local_qgsgeometry_constructor_through_alias(self) -> None:
        source = """def process(points, sink):
    geometry = QgsGeometry.fromPolyline(points)
    result = geometry
    output = QgsFeature()
    output.setGeometry(result)
    sink.addFeature(output)
"""
        candidate = _candidate(5, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["slice_status"], "resolved_local_call_chain")
        self.assertEqual(row["geometry_payload_names"], ["result"])
        self.assertEqual(row["upstream_call_names"], ["QgsGeometry.fromPolyline"])
        self.assertEqual(row["upstream_call_lines"], [2])
        self.assertEqual(row["upstream_signature"], ["qgsgeometry.frompolyline"])
        self.assertFalse(row["training_row_emitted"])

    def test_recovers_inline_geometry_call(self) -> None:
        source = """def process(feature, sink):
    output = QgsFeature()
    output.setGeometry(feature.geometry().centroid())
    sink.addFeature(output)
"""
        candidate = _candidate(3, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["slice_status"], "resolved_local_call_chain")
        self.assertEqual(
            row["upstream_call_names"],
            ["feature.geometry", "feature.geometry.centroid"],
        )

    def test_external_geometry_payload_remains_fail_closed(self) -> None:
        source = """def process(geometry, sink):
    output = QgsFeature()
    output.setGeometry(geometry)
    sink.addFeature(output)
"""
        candidate = _candidate(3, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["slice_status"], "external_payload_no_local_producer")
        self.assertEqual(row["upstream_call_names"], [])

    def test_recovers_equivalent_local_helper_callers(self) -> None:
        source = """class Algorithm:
    def run(self, first, second, sink):
        first_geometry = first.geometry().centroid()
        self.emit(first_geometry, sink)
        second_geometry = second.geometry().centroid()
        self.emit(second_geometry, sink)

    def emit(self, geometry, sink):
        output = QgsFeature()
        output.setGeometry(geometry)
        sink.addFeature(output)
"""
        candidate = _candidate(10, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["slice_status"], "resolved_local_call_chain")
        self.assertEqual(
            row["upstream_call_names"],
            ["first.geometry", "first.geometry.centroid"],
        )
        self.assertTrue(row["caller_payload_provenance"][0]["equivalent_call_sites"])
        self.assertEqual(
            row["caller_payload_provenance"][0]["local_call_site_count"], 2
        )

    def test_different_local_helper_callers_remain_ambiguous(self) -> None:
        source = """class Algorithm:
    def run(self, first, second, sink):
        self.emit(first.geometry().centroid(), sink)
        self.emit(second.geometry().convexHull(), sink)

    def emit(self, geometry, sink):
        output = QgsFeature()
        output.setGeometry(geometry)
        sink.addFeature(output)
"""
        candidate = _candidate(8, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(
            row["slice_status"], "ambiguous_multiple_reaching_definitions"
        )
        self.assertFalse(row["caller_payload_provenance"][0]["equivalent_call_sites"])

    def test_multiple_branch_definitions_remain_ambiguous(self) -> None:
        source = """def process(kind, point, points, sink):
    if kind == 'point':
        geometry = QgsGeometry.fromPoint(point)
    else:
        geometry = QgsGeometry.fromPolyline(points)
    output = QgsFeature()
    output.setGeometry(geometry)
    sink.addFeature(output)
"""
        candidate = _candidate(7, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(
            row["slice_status"], "ambiguous_multiple_reaching_definitions"
        )
        self.assertEqual(
            row["upstream_call_names"],
            ["QgsGeometry.fromPoint", "QgsGeometry.fromPolyline"],
        )

    def test_equivalent_branch_definitions_resolve_to_one_canonical_chain(self) -> None:
        source = """def process(kind, first, second, sink):
    if kind == 'first':
        geometry = first.geometry().centroid()
    else:
        geometry = second.geometry().centroid()
    output = QgsFeature()
    output.setGeometry(geometry)
    sink.addFeature(output)
"""
        candidate = _candidate(7, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["slice_status"], "resolved_local_call_chain")
        self.assertEqual(
            row["upstream_call_names"],
            ["first.geometry", "first.geometry.centroid"],
        )
        self.assertEqual(
            row["equivalent_branch_definitions"],
            [
                {
                    "payload_name": "geometry",
                    "alternative_count": 2,
                    "normalized_call_signature": ["geometry", "centroid"],
                }
            ],
        )

    def test_empty_branch_definitions_remain_ambiguous(self) -> None:
        source = """def process(kind, first, second, sink):
    if kind == 'first':
        geometry = first
    else:
        geometry = second
    output = QgsFeature()
    output.setGeometry(geometry)
    sink.addFeature(output)
"""
        candidate = _candidate(7, hashlib.sha256(source.encode()).hexdigest())

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(
            row["slice_status"], "ambiguous_multiple_reaching_definitions"
        )
        self.assertEqual(row["equivalent_branch_definitions"], [])

    def test_terminal_payload_marks_known_geometry_semantics_report_only(self) -> None:
        source = """def process(feature, sink):
    geometry = feature.geometry().centroid()
    output = QgsFeature(geometry)
    output.setAttributes([])
    sink.addFeature(output)
"""
        candidate = _terminal_only_candidate(
            5, hashlib.sha256(source.encode()).hexdigest()
        )

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["slice_status"], "setgeometry_call_span_not_found")
        self.assertEqual(
            row["terminal_payload_status"], "known_geometry_semantic_candidate"
        )
        self.assertEqual(
            row["terminal_payload_signature"],
            ["geometry", "centroid", "qgsfeature"],
        )
        self.assertFalse(row["training_row_emitted"])

    def test_terminal_payload_keeps_support_only_chain_out_of_candidates(self) -> None:
        source = """def process(feature, sink):
    output = QgsFeature(feature)
    output.setAttributes([])
    sink.addFeature(output)
"""
        candidate = _terminal_only_candidate(
            4, hashlib.sha256(source.encode()).hexdigest()
        )

        row = analyze_candidate_source(candidate, source)

        self.assertEqual(row["terminal_payload_status"], "support_or_custom_only")
        self.assertEqual(row["terminal_payload_signature"], ["qgsfeature"])

    def test_summary_reports_terminal_payload_outcomes(self) -> None:
        rows = [
            {
                "slice_status": "setgeometry_call_span_not_found",
                "terminal_payload_status": "support_or_custom_only",
                "upstream_signature": [],
                "source_authority_key": "body-a",
            },
            {
                "slice_status": "setgeometry_call_span_not_found",
                "terminal_payload_status": "no_local_terminal_payload_chain",
                "upstream_signature": [],
                "source_authority_key": "body-b",
            },
        ]

        summary = build_census(rows)

        self.assertEqual(
            summary["terminal_payload_status_counts"],
            {
                "no_local_terminal_payload_chain": 1,
                "support_or_custom_only": 1,
            },
        )

    def test_rejects_non_mutation_export_candidate(self) -> None:
        source = "output.setGeometry(geometry)\nsink.addFeature(output)\n"
        candidate = _candidate(1, hashlib.sha256(source.encode()).hexdigest())
        candidate["mapping_status"] = "exact_existing_l3"

        with self.assertRaisesRegex(ValueError, "mutation_export_only"):
            analyze_candidate_source(candidate, source)

    def test_rejects_source_sha_mismatch(self) -> None:
        source = "output.setGeometry(geometry)\nsink.addFeature(output)\n"

        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            analyze_candidate_source(_candidate(1, "wrong"), source)

    def test_missing_source_is_retained_as_unavailable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = _candidate(1, "expected-sha")
            candidate["source_path"] = str(Path(directory) / "missing.py")

            row = analyze_candidate_path(candidate)

        self.assertEqual(row["slice_status"], "source_unavailable")
        self.assertEqual(row["source_verification"], "source_file_missing")
        self.assertEqual(row["upstream_call_names"], [])
        self.assertFalse(row["training_row_emitted"])


if __name__ == "__main__":
    unittest.main()
