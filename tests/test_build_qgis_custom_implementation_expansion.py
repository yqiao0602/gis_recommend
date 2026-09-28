from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_qgis_custom_implementation_expansion.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_qgis_custom_implementation_expansion", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _source_row(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "source_path": str(path),
        "source_sha256": digest,
        "content_sha256": digest,
        "source_root_id": "fixture",
        "relative_path": path.name,
    }


def test_load_jsonls_combines_multiple_manifests(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text('{"id": 1}\n', encoding="utf-8")
    second.write_text('{"id": 2}\n', encoding="utf-8")

    assert MODULE._load_jsonls([first, second]) == [{"id": 1}, {"id": 2}]


def test_unresolved_implementation_targets_derive_script_name_ids() -> None:
    assert MODULE._unresolved_implementation_targets(
        [
            {
                "normalization_status": "partially_normalized",
                "unresolved_operator_ids": [
                    "Demo:Exporter",
                    "script:Nested",
                    "dynamic-id-without-provider",
                ],
            },
            {
                "normalization_status": "fully_normalized",
                "unresolved_operator_ids": ["ignored:algorithm"],
            },
        ]
    ) == {"script:exporter", "script:nested"}


def test_build_expansion_clusters_implementation_and_replays_callers(tmp_path: Path) -> None:
    implementation_text = '''
class Inner(QgsProcessingAlgorithm):
    def name(self): return "inner"
    def processAlgorithm(self, parameters, context, feedback):
        buffered = processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
        return processing.run("native:dissolve", {"INPUT": buffered["OUTPUT"]})
'''
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text(implementation_text, encoding="utf-8")
    second.write_text(implementation_text, encoding="utf-8")
    operator_rows = [
        {
            "record_id": "caller-1",
            "source_sha256": "a" * 64,
            "normalization_status": "partially_normalized",
            "original_operator_ids": ["script:inner", "native:fieldcalculator"],
            "unresolved_operator_ids": ["script:inner"],
        }
    ]

    result = MODULE.build_expansion(
        [_source_row(first), _source_row(first), _source_row(second)],
        operator_rows,
        catalog_ids={"native:buffer"},
        mapping={
            "native:buffer": "L3_BUFFER",
            "native:dissolve": "L3_DISSOLVE",
            "native:fieldcalculator": "L3_FIELD",
        },
        target_custom_ids={"script:inner"},
    )

    assert result["summary"]["source_verified_rows"] == 2
    assert result["summary"]["implementation_instance_rows"] == 2
    assert result["summary"]["implementation_variant_rows"] == 1
    assert result["summary"]["fully_expanded_caller_rows"] == 1
    assert result["summary"]["mapping_complete_caller_rows"] == 1
    assert len(result["implementation_instances"][0]["normalized_source_body_sha256"]) == 64
    variant = result["implementation_variants"][0]
    assert variant["algorithm_id"] == "script:inner"
    assert variant["source_instance_count"] == 2
    caller = result["caller_expansions"][0]
    assert caller["expanded_operator_ids"] == [
        "native:buffer",
        "native:dissolve",
        "native:fieldcalculator",
    ]
    assert caller["mapped_l3_chain"] == ["L3_BUFFER", "L3_DISSOLVE", "L3_FIELD"]
    assert caller["source_authority_key"] == f"source_sha256:{'a' * 64}"
    assert caller["training_row_emitted"] is False


def test_build_expansion_fails_closed_on_source_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "implementation.py"
    source.write_text(
        '''
class Inner(QgsProcessingAlgorithm):
    def name(self): return "inner"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )
    row = _source_row(source)
    row["source_sha256"] = "0" * 64

    result = MODULE.build_expansion(
        [row],
        [],
        catalog_ids={"native:buffer"},
        mapping={"native:buffer": "L3_BUFFER"},
        target_custom_ids={"script:inner"},
    )

    assert result["summary"]["source_verified_rows"] == 0
    assert result["summary"]["source_failure_rows"] == 1
    assert result["implementation_instances"] == []
    assert result["source_failures"][0]["source_path_resolution"] == "source_sha256_mismatch"


def test_build_expansion_applies_binding_for_caller_authority(tmp_path: Path) -> None:
    buffer_source = tmp_path / "buffer.py"
    centroid_source = tmp_path / "centroid.py"
    buffer_source.write_text(
        '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )
    centroid_source.write_text(
        '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:centroids", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )
    buffer_body = MODULE.extract_custom_implementations(
        buffer_source.read_text(encoding="utf-8")
    )[0]["implementation_body_sha256"]
    caller_sha = "b" * 64

    result = MODULE.build_expansion(
        [_source_row(buffer_source), _source_row(centroid_source)],
        [
            {
                "record_id": "caller-bound",
                "source_sha256": caller_sha,
                "original_operator_ids": ["script:shared"],
                "unresolved_operator_ids": ["script:shared"],
            }
        ],
        catalog_ids={"native:buffer", "native:centroids"},
        mapping={"native:buffer": "L3_BUFFER", "native:centroids": "L3_POINT"},
        target_custom_ids={"script:shared"},
        implementation_bindings=[
            {
                "caller_source_authority_key": f"source_sha256:{caller_sha}",
                "custom_operator_id": "script:shared",
                "implementation_body_sha256": buffer_body,
            }
        ],
    )

    assert result["summary"]["binding_rows"] == 1
    assert result["summary"]["fully_expanded_caller_rows"] == 1
    assert result["caller_expansions"][0]["expanded_operator_ids"] == [
        "native:buffer"
    ]


def test_build_expansion_allows_provider_custom_id_to_bind_exact_name_variant(
    tmp_path: Path,
) -> None:
    implementation = tmp_path / "provider_algorithm.py"
    implementation.write_text(
        '''
class Exporter(QgsProcessingAlgorithm):
    def name(self): return "exporter"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:savefeatures", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )
    body_hash = MODULE.extract_custom_implementations(
        implementation.read_text(encoding="utf-8")
    )[0]["implementation_body_sha256"]
    caller_sha = "c" * 64

    result = MODULE.build_expansion(
        [_source_row(implementation)],
        [
            {
                "record_id": "provider-caller",
                "source_sha256": caller_sha,
                "original_operator_ids": ["demo:exporter"],
                "unresolved_operator_ids": ["demo:exporter"],
            }
        ],
        catalog_ids={"native:savefeatures"},
        mapping={"native:savefeatures": "L3_EXPORT"},
        target_custom_ids={"demo:exporter"},
        implementation_bindings=[
            {
                "caller_source_authority_key": f"source_sha256:{caller_sha}",
                "custom_operator_id": "demo:exporter",
                "implementation_algorithm_id": "script:exporter",
                "implementation_body_sha256": body_hash,
            }
        ],
    )

    assert result["summary"]["implementation_instance_rows"] == 1
    assert result["summary"]["fully_expanded_caller_rows"] == 1
    assert result["caller_expansions"][0]["expanded_operator_ids"] == [
        "native:savefeatures"
    ]


def test_build_expansion_rejects_conflicting_binding_for_same_caller_custom_id(
    tmp_path: Path,
) -> None:
    implementation = tmp_path / "implementation.py"
    implementation.write_text(
        '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )
    caller_sha = "d" * 64

    import pytest

    with pytest.raises(ValueError, match="conflicting implementation binding"):
        MODULE.build_expansion(
            [_source_row(implementation)],
            [
                {
                    "record_id": "caller-conflict",
                    "source_sha256": caller_sha,
                    "original_operator_ids": ["script:shared"],
                    "unresolved_operator_ids": ["script:shared"],
                }
            ],
            catalog_ids={"native:buffer"},
            mapping={"native:buffer": "L3_BUFFER"},
            target_custom_ids={"script:shared"},
            implementation_bindings=[
                {
                    "caller_source_authority_key": f"source_sha256:{caller_sha}",
                    "custom_operator_id": "script:shared",
                    "implementation_body_sha256": "a" * 64,
                },
                {
                    "caller_source_authority_key": f"source_sha256:{caller_sha}",
                    "custom_operator_id": "script:shared",
                    "implementation_body_sha256": "b" * 64,
                },
            ],
        )


def test_variant_rows_evaluate_each_ambiguous_body_independently(tmp_path: Path) -> None:
    buffer_source = tmp_path / "buffer.py"
    centroid_source = tmp_path / "centroid.py"
    buffer_source.write_text(
        '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )
    centroid_source.write_text(
        '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:centroids", {"INPUT": parameters["INPUT"]})
''',
        encoding="utf-8",
    )

    result = MODULE.build_expansion(
        [_source_row(buffer_source), _source_row(centroid_source)],
        [],
        catalog_ids={"native:buffer", "native:centroids"},
        mapping={"native:buffer": "L3_BUFFER", "native:centroids": "L3_POINT"},
        target_custom_ids={"script:shared"},
    )
    assert {
        tuple(row["expanded_operator_ids"])
        for row in result["implementation_variants"]
        if row["expansion_status"] == "expanded_complete"
    } == {("native:buffer",), ("native:centroids",)}


def test_semantic_operator_authority_is_body_and_call_span_bound(
    tmp_path: Path,
) -> None:
    implementation = tmp_path / "geometry_expression.py"
    implementation.write_text(
        '''
class Buffered(QgsProcessingAlgorithm):
    def name(self): return "buffered"
    def processAlgorithm(self, parameters, context, feedback):
        expression = "buffer($geometry, 'distance', 30, 'round', 'miter', 2)"
        return processing.run(
            "qgis:geometrybyexpression",
            {"INPUT": parameters["INPUT"], "EXPRESSION": expression},
        )
''',
        encoding="utf-8",
    )
    extracted = MODULE.extract_custom_implementations(
        implementation.read_text(encoding="utf-8")
    )[0]
    call = extracted["call_sites"][0]
    authority = {
        "implementation_body_sha256": extracted["implementation_body_sha256"],
        "line_start": call["line_start"],
        "line_end": call["line_end"],
        "raw_operator_id": "qgis:geometrybyexpression",
        "resolved_operator_id": "native:buffer",
        "rule_id": "geometrybyexpression:buffer:source-reviewed-v1",
    }

    resolved = MODULE.build_expansion(
        [_source_row(implementation)],
        [],
        catalog_ids={"qgis:geometrybyexpression", "native:buffer"},
        mapping={"native:buffer": "L3_BUFFER"},
        target_custom_ids={"script:buffered"},
        semantic_operator_authority=[authority],
    )

    assert resolved["summary"]["semantic_operator_resolved_call_rows"] == 1
    assert resolved["implementation_variants"][0]["expanded_operator_ids"] == [
        "native:buffer"
    ]
    assert resolved["implementation_variants"][0]["semantic_operator_resolutions"] == [
        {
            "line_start": call["line_start"],
            "line_end": call["line_end"],
            "raw_operator_id": "qgis:geometrybyexpression",
            "resolved_operator_id": "native:buffer",
            "rule_id": "geometrybyexpression:buffer:source-reviewed-v1",
        }
    ]

    mismatched = MODULE.build_expansion(
        [_source_row(implementation)],
        [],
        catalog_ids={"qgis:geometrybyexpression", "native:buffer"},
        mapping={"native:buffer": "L3_BUFFER"},
        target_custom_ids={"script:buffered"},
        semantic_operator_authority=[{**authority, "line_start": 999, "line_end": 999}],
    )
    assert mismatched["summary"]["semantic_operator_resolved_call_rows"] == 0
    assert mismatched["implementation_variants"][0]["semantic_operator_resolutions"] == []
    assert mismatched["implementation_variants"][0]["expanded_operator_ids"] != [
        "native:buffer"
    ]

def test_build_expansion_replays_complete_custom_scope_into_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "connected_custom.py"
    source.write_text(
        '''
class Connected(QgsProcessingAlgorithm):
    def name(self): return "connected"
    def processAlgorithm(self, parameters, context, feedback):
        buffered = processing.run(
            "native:buffer",
            {"INPUT": parameters["INPUT"], "DISTANCE": 25, "OUTPUT": "TEMPORARY_OUTPUT"},
        )
        return processing.run(
            "native:dissolve",
            {"INPUT": buffered["OUTPUT"], "OUTPUT": parameters["OUTPUT"]},
        )
''',
        encoding="utf-8",
    )

    result = MODULE.build_expansion(
        [_source_row(source)],
        [],
        catalog_ids={"native:buffer", "native:dissolve"},
        mapping={"native:buffer": "L3_BUFFER", "native:dissolve": "L3_DISSOLVE"},
        target_custom_ids={"script:connected"},
    )

    assert result["summary"]["scope_parent_rows"] == 1
    assert result["summary"]["scope_candidate_rows"] == 1
    assert result["summary"]["scope_canonical_rows"] == 1
    candidate = result["scope_dedup_ledger"][0]
    assert candidate["dedup_status"] == "canonical_candidate"
    assert candidate["operator_ids"] == ["native:buffer", "native:dissolve"]
    assert candidate["mapped_l3_chain"] == ["L3_BUFFER", "L3_DISSOLVE"]
    assert candidate["description_fidelity_passed"] is True
