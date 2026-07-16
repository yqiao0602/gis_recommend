# QGIS Source-Grounded Extractor v2.1 Precision Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicitly selected, deterministic Extractor v2.1 that removes the confirmed v1 false positives, closes the reviewed bounded-identity gaps, records every suppression decision, and passes the locked 35-record precision gate without changing stable v1 behavior.

**Architecture:** Keep `compile_source_grounded_record()` as the frozen v1 baseline. The v2.1 compiler first applies source and class-role gates, then runs v1 extraction and performs a deterministic, auditable post-processing pass over evidence IDs: reject non-workflow sources, filter invalid E1/E3 classes, suppress constructors and implementation substeps, correct bounded identities, and merge only semantically identical steps. A separate gate evaluator converts the locked adjudications into expected operator/custom multisets and reports hard-gate metrics without granting taxonomy or training admission.

**Tech Stack:** Python 3.9+, standard library (`ast`-shaped mappings, `collections.Counter`, `json`, `re`, `unittest`), existing `gis_recommend.data.qgis_pilot` normalization helpers, existing source-grounded v1 extractor and CLI.

---

## Scope And Constraints

- v1 remains the default CLI profile and its existing semantic output stays unchanged.
- v2.1 is activated only with `--extractor-profile v2`.
- No LLM/API calls, model training, taxonomy mutation, SFT rows, split files, or sample duplication.
- No writes under `/home/yll`; server reads may use `/home/yll`, while all outputs go under `/home/qy/system_redesign`.
- Existing v1 report directories remain immutable. Every v2 run uses a new versioned output directory.
- All emitted operator IDs must be provider-qualified and present in the supplied catalog.
- Rejected sources and classes remain visible through structured audit fields and emit zero positive items.
- v2.2 custom-function call-graph recovery is outside this plan. v2.1 may preserve accepted class-level custom identities, but it does not recover module-level functions.

## File Map

| File | Responsibility |
| --- | --- |
| `src/gis_recommend/data/qgis_source_quality.py` | Structural source-quality gate and E3/E1 class-role classifier. No operator mapping. |
| `src/gis_recommend/data/qgis_source_grounded_v2.py` | v2.1 orchestration, evidence-index construction, constructor suppression, bounded identity corrections, class filtering, implementation-substep suppression, semantic duplicate merging, output contract validation. |
| `src/gis_recommend/data/qgis_source_grounded_gate.py` | Locked-adjudication gold construction, item matching, tier/overall precision, completeness, false-positive counters, hard-gate decision. |
| `scripts/run_qgis_source_grounded_extractor.py` | Add profile selection, v2 compiler dispatch, profile/schema metadata, v2 audit workbook columns, v2 gate summary and code hashes. |
| `tests/test_qgis_source_grounded_v1_compat.py` | Frozen v1 compatibility assertions, including known constructor behavior that must remain isolated to v1. |
| `tests/test_qgis_source_quality.py` | Source and class-role decision matrix. |
| `tests/test_qgis_source_grounded_v2.py` | v2.1 rule-level compiler tests. |
| `tests/test_qgis_source_grounded_gate.py` | Gold multiset construction, precision accounting and hard-gate tests. |
| `tests/test_qgis_source_grounded_cli.py` | Default/explicit profile parity, v2 metadata, rejected-source artifacts, gate summary and fail-closed CLI behavior. |
| `docs/reports/qgis_pilot/phase5_source_grounded_extractor_v2/v2_1_locked_35_regression/` | New locked-35 v2.1 outputs after all local rule tests pass. Never overwrite earlier runs. |

## Data Contracts

### Source-Quality Decision

```python
{
    "decision": "rejected_test",
    "accepted": False,
    "signals": {
        "path_test_signal": True,
        "test_method_count": 3,
        "assertion_count": 4,
        "mock_signal_count": 0,
        "provider_signal_count": 0,
        "ui_signal_count": 0,
        "execution_method_count": 0,
        "semantic_call_count": 2,
    },
    "reasons": ["path_and_structural_test_evidence"],
}
```

Allowed decisions are:

```python
SOURCE_DECISIONS = {
    "accepted_workflow",
    "rejected_test",
    "rejected_mock_or_example",
    "rejected_provider_only",
    "rejected_ui_only",
    "accepted_mixed_ui_workflow",
}
```

### Class-Role Decision

```python
{
    "class_name": "ImportPrismaL1Algorithm",
    "line": 12,
    "role": "algorithm",
    "may_emit_identity": True,
    "signals": {
        "processing_base": True,
        "process_algorithm_method": True,
        "execution_method_count": 1,
        "semantic_call_count": 7,
        "test_method_count": 0,
        "ui_signal_count": 0,
    },
    "reasons": ["processing_base_and_process_algorithm"],
}
```

Only `algorithm` and `domain_orchestrator` set `may_emit_identity=True`.

### v2.1 Extraction Additions

Every v2 record includes these fields in addition to the existing v1 audit surface:

```python
{
    "extractor_profile": "v2",
    "extractor_schema_version": "qgis_source_grounded_extraction_v2_1",
    "source_quality_decision": {},
    "class_role_decisions": [],
    "bounded_identity_decisions": [],
    "suppressed_evidence": [],
    "duplicate_groups": [],
    "unresolved_evidence": [],
    "workflow_completeness_diagnostics": {},
    "taxonomy_admission": "not_granted",
    "training_admission": "not_granted",
    "training_rows_emitted": 0,
}
```

## Test Specification

| Area | Required cases | Pass condition |
| --- | --- | --- |
| v1 isolation | Constructor still emits v1 reproject; default profile equals explicit v1; current focused suites | No v1 chain or audit regression |
| Source gate | Real workflow, structural test, mock/example, provider-only, UI-only, mixed UI/workflow | Correct decision; every rejection emits zero positive items |
| Class roles | Processing algorithm, domain importer, helper, data container, provider, mock, test, GUI shell, unresolved | Only algorithm/orchestrator may emit E1/E3 identity |
| Constructor suppression | `QgsCoordinateTransform(...)`, Processing parameter/options objects, registry/provider construction; real `transform`, `transformBoundingBox`, `gdal.Warp` | Constructors audited but absent from all positive chains; execution calls remain |
| Identity gaps | `gdal.ComputeProximity`, `gdal_merge.main`, explicit `qgis:rastersampling`, legacy Eliminate, expression selection, vector writer export, Shapely polygonize | Exact reviewed provider identity or abstention; no suffix-only fallback |
| Identity precedence | E0 over E1/E2, bounded class over internal E2, independent E0 output preserved | High-level identity is primary; internal substeps are audit-only |
| Duplicate merge | AST/steps same call, macro/micro same semantic step, same-input/same-output BuildVRT; different outputs and repeated transforms | Only true duplicates merge; distinct products remain distinct |
| Output contract | Invalid role, unknown operator, missing evidence ID, malformed duplicate group, attempted admission | v2 contract raises and CLI returns code 2 |
| Locked gate | 35 adjudications, all tiers, rejected tests, transform constructors, completeness | E0 >=80%, E2 >=85%, E3 >=70%, overall >=80%, test FP=0, constructor FP=0, completeness >=25.7% |
| Compatibility | Focused extractor tests and stable-94 `test_qgis*.py` | All green; no production default change |

---

### Task 1: Freeze v1 Compatibility Before Adding v2

**Files:**
- Create: `tests/test_qgis_source_grounded_v1_compat.py`
- Test: `tests/test_qgis_source_grounded_semantic_compiler.py`

- [ ] **Step 1: Add a v1 contract test that locks the known constructor behavior**

```python
import unittest

from gis_recommend.data.qgis_source_grounded_extractor import (
    compile_source_grounded_record,
)


class QgisSourceGroundedV1CompatibilityTests(unittest.TestCase):
    def test_v1_constructor_mapping_remains_frozen_for_profile_isolation(self):
        result = compile_source_grounded_record(
            {"type": "Module", "body": []},
            [
                {
                    "evidence_id": "constructor",
                    "statement_index": 1,
                    "operation": "QgsCoordinateTransform",
                    "channel": "direct_api",
                },
                {
                    "evidence_id": "execution",
                    "statement_index": 2,
                    "operation": "QgsCoordinateTransform.transformBoundingBox",
                    "channel": "direct_api",
                },
            ],
            {"native:reprojectlayer": {}},
        )

        self.assertEqual(
            result["operator_chain"],
            ["native:reprojectlayer", "native:reprojectlayer"],
        )

    def test_v1_preserves_distinct_buildvrt_outputs(self):
        steps = [
            {
                "evidence_id": "vrt-a",
                "statement_index": 1,
                "operation": "gdal.BuildVRT",
                "channel": "direct_api",
                "input_roles": ["band_1", "band_2"],
                "output_roles": ["stack_a.vrt"],
            },
            {
                "evidence_id": "vrt-b",
                "statement_index": 2,
                "operation": "gdal.BuildVRT",
                "channel": "direct_api",
                "input_roles": ["band_1", "band_2"],
                "output_roles": ["stack_b.vrt"],
            },
        ]

        result = compile_source_grounded_record(
            {"type": "Module", "body": []},
            steps,
            {"gdal:buildvirtualraster": {}},
        )

        self.assertEqual(
            result["operator_chain"],
            ["gdal:buildvirtualraster", "gdal:buildvirtualraster"],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the compatibility test and confirm the current v1 behavior is captured**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v1_compat -v
```

Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 3: Run the existing focused extractor baseline**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_extractor tests.test_qgis_source_grounded_semantic_compiler tests.test_qgis_source_grounded_cli -v
```

Expected: all existing tests pass before v2 files are introduced.

- [ ] **Step 4: Commit the frozen contract**

```powershell
git add tests/test_qgis_source_grounded_v1_compat.py
git commit -m "Protect the frozen extractor while precision work proceeds" -m "The v2 path must correct constructor and duplicate behavior without changing the stable v1 compiler." -m "Constraint: v1 remains the default profile" -m "Confidence: high" -m "Scope-risk: narrow" -m "Directive: Keep v2 corrections out of qgis_source_grounded_extractor.py unless this contract remains green" -m "Tested: v1 compatibility and focused extractor suites"
```

### Task 2: Implement The Structural Source-Quality Gate

**Files:**
- Create: `src/gis_recommend/data/qgis_source_quality.py`
- Create: `tests/test_qgis_source_quality.py`

- [ ] **Step 1: Write failing source-decision tests**

```python
import unittest

from gis_recommend.data.qgis_source_quality import classify_source_quality


def function(name, calls=()):
    return {
        "type": "FunctionDef",
        "name": name,
        "body": [
            {
                "type": "Expr",
                "value": {
                    "type": "Call",
                    "func": {"type": "Name", "id": call},
                    "args": [],
                },
            }
            for call in calls
        ],
    }


class QgisSourceQualityTests(unittest.TestCase):
    def test_rejects_structural_test_source_even_when_geometry_calls_exist(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "TestGeometryTools",
                    "bases": [{"type": "Name", "id": "unittest.TestCase"}],
                    "body": [function("test_union", ("QgsGeometry.combine", "self.assertEqual"))],
                }
            ],
        }

        decision = classify_source_quality(ast_record, "tests/test_geometry_tools.py")

        self.assertEqual(decision["decision"], "rejected_test")
        self.assertFalse(decision["accepted"])

    def test_rejects_provider_only_source(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "PluginProvider",
                    "bases": [{"type": "Name", "id": "QgsProcessingProvider"}],
                    "body": [function("loadAlgorithms", ("self.addAlgorithm",))],
                }
            ],
        }

        decision = classify_source_quality(ast_record, "plugin/provider.py")

        self.assertEqual(decision["decision"], "rejected_provider_only")

    def test_rejects_ui_shell_without_domain_execution(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "SettingsDialog",
                    "bases": [{"type": "Name", "id": "QDialog"}],
                    "body": [function("accept", ("self.close",))],
                }
            ],
        }

        decision = classify_source_quality(ast_record, "plugin/settings_dialog.py")

        self.assertEqual(decision["decision"], "rejected_ui_only")

    def test_accepts_mixed_ui_importer_that_executes_domain_work(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GpsImporter",
                    "bases": [{"type": "Name", "id": "QDialog"}],
                    "body": [
                        function("accept", ("self.importGpx",)),
                        function("importGpx", ("QgsCoordinateTransform.transformBoundingBox", "QgsVectorLayer")),
                    ],
                }
            ],
        }

        decision = classify_source_quality(ast_record, "plugin/gps_importer.py")

        self.assertEqual(decision["decision"], "accepted_mixed_ui_workflow")
        self.assertTrue(decision["accepted"])

    def test_accepts_processing_workflow_without_filename_hints(self):
        ast_record = {
            "type": "Module",
            "body": [function("run", ("processing.run",))],
        }

        decision = classify_source_quality(ast_record, "script_123.py")

        self.assertEqual(decision["decision"], "accepted_workflow")
```

- [ ] **Step 2: Run the source tests and verify the missing module failure**

Run:

```powershell
python -m unittest tests.test_qgis_source_quality.QgisSourceQualityTests -v
```

Expected: import failure for `gis_recommend.data.qgis_source_quality`.

- [ ] **Step 3: Implement deterministic signal collection and ordered decisions**

Implement these constants and public function in `qgis_source_quality.py`:

```python
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from gis_recommend.data.qgis_pilot import classify_qgis_api_call


SOURCE_DECISIONS = {
    "accepted_workflow",
    "rejected_test",
    "rejected_mock_or_example",
    "rejected_provider_only",
    "rejected_ui_only",
    "accepted_mixed_ui_workflow",
}

_TEST_PATH = re.compile(r"(^|[/\\])(tests?|testing)([/\\]|$)|(^|[/\\])test_[^/\\]+\.py$|_test\.py$")
_TEST_METHOD = re.compile(r"^test(_|$)")
_MOCK_NAME = re.compile(r"(mock|fake|stub|dummy)", re.IGNORECASE)
_EXAMPLE_PATH = re.compile(r"(^|[/\\])(examples?|demos?)([/\\]|$)", re.IGNORECASE)
_UI_BASE = re.compile(r"(dialog|dockwidget|widget|mainwindow)$", re.IGNORECASE)
_EXECUTION_METHOD = re.compile(r"^(processalgorithm|run|execute|import|export|analy[sz]e|build|create|convert|calculate)", re.IGNORECASE)
_UI_METHODS = {"initgui", "unload", "showevent", "closeevent", "accept", "reject", "setupui"}
_PROVIDER_METHODS = {"loadalgorithms", "addalgorithm", "refreshalgorithms", "supportsnonfilebasedoutput"}


def _walk(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _node_type(node: Mapping[str, Any]) -> str:
    return str(node.get("type") or node.get("_type") or "")


def _name(node: Any) -> str:
    if not isinstance(node, Mapping):
        return ""
    if _node_type(node) == "Name":
        return str(node.get("id") or "")
    if _node_type(node) == "Attribute":
        parent = _name(node.get("value"))
        attr = str(node.get("attr") or "")
        return ".".join(value for value in (parent, attr) if value)
    return ""


def _call_name(node: Mapping[str, Any]) -> str:
    return _name(node.get("func")) if _node_type(node) == "Call" else ""


def _source_signals(ast_record: Mapping[str, Any], source_path: str) -> dict[str, Any]:
    methods = []
    bases = []
    calls = []
    assertion_count = 0
    for node in _walk(ast_record):
        kind = _node_type(node)
        if kind in {"FunctionDef", "AsyncFunctionDef"}:
            methods.append(str(node.get("name") or "").lower())
        elif kind == "ClassDef":
            bases.extend(_name(base).lower() for base in node.get("bases") or [])
        elif kind == "Assert":
            assertion_count += 1
        elif kind == "Call":
            call = _call_name(node).lower()
            calls.append(call)
            if call.startswith(("self.assert", "pytest.", "numpy.testing.")):
                assertion_count += 1

    semantic_call_count = sum(
        classify_qgis_api_call({"operation": call, "channel": "direct_api"})["category"]
        in {"processing_operator", "semantic_anchor"}
        for call in calls
    )
    return {
        "path_test_signal": bool(_TEST_PATH.search(source_path.replace("\\", "/"))),
        "path_example_signal": bool(_EXAMPLE_PATH.search(source_path.replace("\\", "/"))),
        "test_method_count": sum(bool(_TEST_METHOD.match(method)) for method in methods),
        "assertion_count": assertion_count,
        "mock_signal_count": sum(bool(_MOCK_NAME.search(value)) for value in methods + bases + calls),
        "provider_signal_count": sum("processingprovider" in base for base in bases)
        + sum(call.rpartition(".")[2] in _PROVIDER_METHODS for call in calls),
        "ui_signal_count": sum(bool(_UI_BASE.search(base)) for base in bases)
        + sum(method in _UI_METHODS for method in methods),
        "execution_method_count": sum(bool(_EXECUTION_METHOD.match(method)) for method in methods),
        "semantic_call_count": semantic_call_count,
    }


def classify_source_quality(
    ast_record: Mapping[str, Any], source_path: str
) -> dict[str, Any]:
    signals = _source_signals(ast_record, source_path)
    strong_test = (
        signals["test_method_count"] >= 2
        or signals["assertion_count"] >= 2
        or (
            signals["path_test_signal"]
            and (signals["test_method_count"] >= 1 or signals["assertion_count"] >= 1)
        )
    )
    has_execution = signals["execution_method_count"] > 0 or signals["semantic_call_count"] > 0

    if strong_test:
        decision, reasons = "rejected_test", ["path_and_structural_test_evidence"]
    elif signals["provider_signal_count"] > 0 and not has_execution:
        decision, reasons = "rejected_provider_only", ["provider_registration_without_domain_execution"]
    elif signals["ui_signal_count"] > 0 and has_execution:
        decision, reasons = "accepted_mixed_ui_workflow", ["ui_owner_with_domain_execution"]
    elif signals["ui_signal_count"] > 0:
        decision, reasons = "rejected_ui_only", ["ui_lifecycle_without_domain_execution"]
    elif (signals["mock_signal_count"] > 0 or signals["path_example_signal"]) and not has_execution:
        decision, reasons = "rejected_mock_or_example", ["mock_or_example_without_domain_execution"]
    elif has_execution:
        decision, reasons = "accepted_workflow", ["domain_execution_evidence"]
    else:
        decision, reasons = "rejected_mock_or_example", ["no_executable_workflow_evidence"]

    return {
        "decision": decision,
        "accepted": decision.startswith("accepted_"),
        "signals": signals,
        "reasons": reasons,
    }
```

- [ ] **Step 4: Run the source-decision tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_quality.QgisSourceQualityTests -v
```

Expected: all five source-decision tests pass.

- [ ] **Step 5: Commit the source gate**

```powershell
git add src/gis_recommend/data/qgis_source_quality.py tests/test_qgis_source_quality.py
git commit -m "Reject non-workflow QGIS sources before operator emission" -m "The blind holdout showed test, provider and UI sources producing positive operators, so v2.1 now requires structural workflow evidence before compilation." -m "Constraint: filename tokens alone cannot decide acceptance" -m "Rejected: Record-ID denylist | it would not generalize beyond the locked holdout" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: source-quality decision matrix"
```

### Task 3: Implement The E1/E3 Class-Role Classifier

**Files:**
- Modify: `src/gis_recommend/data/qgis_source_quality.py`
- Modify: `tests/test_qgis_source_quality.py`

- [ ] **Step 1: Add failing class-role tests**

Add cases that assert the exact roles below:

```python
from gis_recommend.data.qgis_source_quality import classify_class_roles


class QgisClassRoleTests(unittest.TestCase):
    def _class(self, name, base, methods):
        return {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": name,
                    "lineno": 5,
                    "bases": [{"type": "Name", "id": base}] if base else [],
                    "body": methods,
                }
            ],
        }

    def test_processing_algorithm_may_emit_identity(self):
        decisions = classify_class_roles(
            self._class(
                "ImportPrismaL1Algorithm",
                "QgsProcessingAlgorithm",
                [function("processAlgorithm", ("gdal.BuildVRT",))],
            )
        )
        self.assertEqual(decisions[0]["role"], "algorithm")
        self.assertTrue(decisions[0]["may_emit_identity"])

    def test_domain_importer_may_emit_identity(self):
        decisions = classify_class_roles(
            self._class("GpsImporter", "QDialog", [function("importGpx", ("QgsCoordinateTransform.transformBoundingBox",))])
        )
        self.assertEqual(decisions[0]["role"], "domain_orchestrator")
        self.assertTrue(decisions[0]["may_emit_identity"])

    def test_data_container_cannot_emit_identity(self):
        decisions = classify_class_roles(
            self._class("Inputdata", "object", [function("__init__")])
        )
        self.assertEqual(decisions[0]["role"], "data_container")
        self.assertFalse(decisions[0]["may_emit_identity"])

    def test_test_provider_mock_helper_and_gui_roles_are_rejected(self):
        cases = [
            ("TestGeometry", "unittest.TestCase", [function("test_union", ("self.assertEqual",))], "test"),
            ("PluginProvider", "QgsProcessingProvider", [function("loadAlgorithms", ("self.addAlgorithm",))], "provider"),
            ("FakeLayer", "object", [function("featureCount")], "mock"),
            ("GeometryHelper", "object", [function("formatWkt")], "helper"),
            ("SettingsDialog", "QDialog", [function("accept", ("self.close",))], "gui_shell"),
        ]
        for name, base, methods, expected in cases:
            with self.subTest(name=name):
                decision = classify_class_roles(self._class(name, base, methods))[0]
                self.assertEqual(decision["role"], expected)
                self.assertFalse(decision["may_emit_identity"])
```

- [ ] **Step 2: Run the role tests and verify `classify_class_roles` is missing**

Run:

```powershell
python -m unittest tests.test_qgis_source_quality.QgisClassRoleTests -v
```

Expected: import failure for `classify_class_roles`.

- [ ] **Step 3: Add ordered class-role rules**

Add these public constants and functions to `qgis_source_quality.py`:

```python
CLASS_ROLES = {
    "algorithm",
    "domain_orchestrator",
    "helper",
    "data_container",
    "provider",
    "mock",
    "test",
    "gui_shell",
    "unresolved",
}

_PROCESSING_BASE = re.compile(r"(qgsprocessingalgorithm|qgisalgorithm|gdalalgorithm|geoalgorithm)$", re.IGNORECASE)
_PROVIDER_BASE = re.compile(r"processingprovider$", re.IGNORECASE)
_TEST_BASE = re.compile(r"(testcase|qgstest)$", re.IGNORECASE)
_PASSIVE_METHODS = {"__init__", "__repr__", "__str__", "get", "set", "copy", "clone"}


def _class_signals(class_node: Mapping[str, Any]) -> dict[str, Any]:
    methods = [
        str(node.get("name") or "")
        for node in class_node.get("body") or []
        if isinstance(node, Mapping)
        and _node_type(node) in {"FunctionDef", "AsyncFunctionDef"}
    ]
    bases = [_name(base) for base in class_node.get("bases") or []]
    calls = [
        _call_name(node).lower()
        for node in _walk(class_node.get("body") or [])
        if _node_type(node) == "Call"
    ]
    semantic_call_count = sum(
        classify_qgis_api_call({"operation": call, "channel": "direct_api"})["category"]
        in {"processing_operator", "semantic_anchor"}
        for call in calls
    )
    lower_methods = [method.lower() for method in methods]
    return {
        "bases": bases,
        "methods": methods,
        "processing_base": any(_PROCESSING_BASE.search(base) for base in bases),
        "provider_base": any(_PROVIDER_BASE.search(base) for base in bases),
        "test_base": any(_TEST_BASE.search(base) for base in bases),
        "process_algorithm_method": "processalgorithm" in lower_methods,
        "execution_method_count": sum(bool(_EXECUTION_METHOD.match(method)) for method in lower_methods),
        "semantic_call_count": semantic_call_count,
        "test_method_count": sum(bool(_TEST_METHOD.match(method)) for method in lower_methods),
        "assertion_count": sum(call.startswith(("self.assert", "pytest.")) for call in calls),
        "mock_name": bool(_MOCK_NAME.search(str(class_node.get("name") or ""))),
        "ui_signal_count": sum(bool(_UI_BASE.search(base)) for base in bases)
        + sum(method in _UI_METHODS for method in lower_methods),
        "provider_method_count": sum(method in _PROVIDER_METHODS for method in lower_methods),
        "passive_only": bool(methods)
        and all(method.lower() in _PASSIVE_METHODS or method.lower().startswith(("get", "set")) for method in methods),
    }


def classify_class_roles(ast_record: Mapping[str, Any]) -> list[dict[str, Any]]:
    decisions = []
    for node in _walk(ast_record):
        if _node_type(node) != "ClassDef":
            continue
        signals = _class_signals(node)
        name = str(node.get("name") or "")
        if signals["test_base"] or signals["test_method_count"] >= 1 or signals["assertion_count"] >= 1:
            role, reasons = "test", ["test_structure"]
        elif signals["mock_name"]:
            role, reasons = "mock", ["mock_class_name"]
        elif signals["provider_base"] or signals["provider_method_count"] > 0:
            role, reasons = "provider", ["provider_registration_role"]
        elif signals["processing_base"] or signals["process_algorithm_method"]:
            role, reasons = "algorithm", ["processing_base_and_process_algorithm"]
        elif signals["semantic_call_count"] > 0 and signals["execution_method_count"] > 0:
            role, reasons = "domain_orchestrator", ["owns_domain_execution"]
        elif signals["ui_signal_count"] > 0:
            role, reasons = "gui_shell", ["ui_lifecycle_without_owned_domain_execution"]
        elif signals["passive_only"]:
            role, reasons = "data_container", ["passive_state_container"]
        elif signals["methods"]:
            role, reasons = "helper", ["methods_without_owned_domain_execution"]
        else:
            role, reasons = "unresolved", ["insufficient_class_evidence"]
        decisions.append(
            {
                "class_name": name,
                "line": node.get("lineno"),
                "role": role,
                "may_emit_identity": role in {"algorithm", "domain_orchestrator"},
                "signals": {key: value for key, value in signals.items() if key not in {"bases", "methods"}},
                "reasons": reasons,
            }
        )
    return decisions
```

- [ ] **Step 4: Run all quality and role tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_quality -v
```

Expected: all source and class-role cases pass.

- [ ] **Step 5: Commit the role classifier**

```powershell
git add src/gis_recommend/data/qgis_source_quality.py tests/test_qgis_source_quality.py
git commit -m "Separate executable QGIS classes from structural support code" -m "E3 precision was dominated by tests, containers, providers and GUI shells, so class identity now requires owned domain execution." -m "Constraint: names alone are insufficient except explicit mock/test markers combined with structure" -m "Confidence: medium" -m "Scope-risk: moderate" -m "Directive: Extend role rules with reusable structural evidence, never record IDs" -m "Tested: nine-role decision matrix"
```

### Task 4: Add The Isolated v2.1 Compiler And Audit Contract

**Files:**
- Create: `src/gis_recommend/data/qgis_source_grounded_v2.py`
- Create: `tests/test_qgis_source_grounded_v2.py`

- [ ] **Step 1: Write failing tests for source rejection and class filtering**

```python
import unittest

from gis_recommend.data.qgis_source_grounded_v2 import (
    compile_source_grounded_record_v2,
)


class QgisSourceGroundedV2Tests(unittest.TestCase):
    def test_rejected_test_source_emits_no_positive_items(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "TestGeometry",
                    "bases": [{"type": "Name", "id": "unittest.TestCase"}],
                    "body": [
                        {"type": "FunctionDef", "name": "test_union", "body": []},
                        {"type": "FunctionDef", "name": "test_difference", "body": []},
                    ],
                }
            ],
        }
        result = compile_source_grounded_record_v2(
            ast_record,
            [{"evidence_id": "union", "operation": "QgsGeometry.combine", "channel": "direct_api"}],
            {"native:union": {}},
            source_path="tests/test_geometry.py",
        )

        self.assertEqual(result["source_quality_decision"]["decision"], "rejected_test")
        self.assertEqual(result["operator_chain"], [])
        self.assertEqual(result["custom_components"], [])
        self.assertEqual(result["training_rows_emitted"], 0)

    def test_filters_data_container_but_preserves_real_algorithm(self):
        ast_record = {
            "type": "Module",
            "body": [
                {"type": "ClassDef", "name": "Inputdata", "bases": [], "body": [{"type": "FunctionDef", "name": "__init__", "body": []}]},
                {
                    "type": "ClassDef",
                    "name": "RasterMathAlgorithm",
                    "bases": [{"type": "Name", "id": "QgsProcessingAlgorithm"}],
                    "body": [{"type": "FunctionDef", "name": "processAlgorithm", "body": []}],
                },
            ],
        }
        result = compile_source_grounded_record_v2(
            ast_record,
            [{"evidence_id": "vrt", "operation": "gdal.BuildVRT", "channel": "direct_api"}],
            {"gdal:buildvirtualraster": {}},
            source_path="raster_math.py",
        )

        self.assertEqual([item["class_name"] for item in result["custom_components"]], ["RasterMathAlgorithm"])
        self.assertEqual(result["operator_chain"], ["gdal:buildvirtualraster"])
```

- [ ] **Step 2: Run the v2 tests and verify the missing module failure**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v2 -v
```

Expected: import failure for `qgis_source_grounded_v2`.

- [ ] **Step 3: Implement v1-backed v2 orchestration without modifying v1**

Create the following public entry point and record finalizer. The compiler must call `classify_source_quality()` before v1 compilation and must call `compile_source_grounded_record()` only for accepted sources.

```python
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from gis_recommend.data.qgis_source_grounded_extractor import (
    compile_source_grounded_record,
)
from gis_recommend.data.qgis_source_quality import (
    CLASS_ROLES,
    SOURCE_DECISIONS,
    classify_class_roles,
    classify_source_quality,
)


V2_SCHEMA_VERSION = "qgis_source_grounded_extraction_v2_1"
_PROVIDER_QUALIFIED_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$")


class QgisSourceGroundedV2Error(RuntimeError):
    pass


def _empty_v2_record(source_decision, class_roles, task_text_provenance):
    return {
        "explicit_operators": [],
        "unresolved_explicit_ids": [],
        "class_operators": [],
        "custom_components": [],
        "ast_operator_events": [],
        "operator_chain": [],
        "operator_evidence": [],
        "parallel_ast_operator_chain": [],
        "parallel_ast_operator_evidence": [],
        "supporting_operator_chain": [],
        "supporting_operator_evidence": [],
        "cross_source_ordering": "source_rejected",
        "unsupported_evidence": [],
        "evidence_tiers": [],
        "confidence": None,
        "reviewer_status": "pending_human_review",
        "task_text_provenance": dict(task_text_provenance or {"status": "not_provided"}),
        "source_quality_decision": source_decision,
        "class_role_decisions": class_roles,
        "bounded_identity_decisions": [],
        "suppressed_evidence": [],
        "duplicate_groups": [],
        "unresolved_evidence": [],
        "workflow_completeness_diagnostics": {
            "positive_item_count": 0,
            "source_rejected": True,
        },
        "extractor_profile": "v2",
        "extractor_schema_version": V2_SCHEMA_VERSION,
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
    }


def _accepted_class_keys(class_roles):
    return {
        (item["class_name"], item.get("line"))
        for item in class_roles
        if item["may_emit_identity"]
    }


def _filter_class_identity(base, class_roles):
    accepted = _accepted_class_keys(class_roles)
    base["class_operators"] = [
        item
        for item in base["class_operators"]
        if (item["class_name"], item.get("line")) in accepted
    ]
    base["custom_components"] = [
        item
        for item in base["custom_components"]
        if (item["class_name"], item.get("line")) in accepted
    ]
    accepted_e1 = {
        (item["operator_id"], item.get("line"))
        for item in base["class_operators"]
    }
    base["ast_operator_events"] = [
        item
        for item in base["ast_operator_events"]
        if item["evidence_tier"] != "E1"
        or (item["operator_id"], item.get("line")) in accepted_e1
    ]
    for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence"):
        base[key] = [
            item
            for item in base[key]
            if item["evidence_tier"] != "E1"
            or (item["operator_id"], item.get("line")) in accepted_e1
        ]
    if not any(item["evidence_tier"] == "E1" for item in base["operator_evidence"]):
        if base["cross_source_ordering"] == "e1_authoritative":
            base["operator_evidence"] = list(base["supporting_operator_evidence"])
            base["supporting_operator_evidence"] = []
            base["cross_source_ordering"] = "ordered_steps_only"


def _refresh_derived_fields(record):
    record["operator_chain"] = [item["operator_id"] for item in record["operator_evidence"]]
    record["parallel_ast_operator_chain"] = [item["operator_id"] for item in record["parallel_ast_operator_evidence"]]
    record["supporting_operator_chain"] = [item["operator_id"] for item in record["supporting_operator_evidence"]]
    tiers = {
        item["evidence_tier"]
        for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence")
        for item in record[key]
    }
    if record["custom_components"]:
        tiers.add("E3")
    record["evidence_tiers"] = sorted(tiers)
    confidences = [item["confidence"] for item in record["operator_evidence"]]
    record["confidence"] = min(confidences) if confidences else None
    record["workflow_completeness_diagnostics"] = {
        "positive_item_count": len(record["operator_evidence"]) + len(record["custom_components"]),
        "source_rejected": False,
        "unresolved_count": len(record["unresolved_evidence"]),
        "suppressed_count": len(record["suppressed_evidence"]),
        "duplicate_group_count": len(record["duplicate_groups"]),
    }


def compile_source_grounded_record_v2(
    ast_record: Mapping[str, Any],
    ordered_steps: list[Mapping[str, Any]],
    catalog: Mapping[str, Any],
    *,
    source_path: str,
    task_text_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_decision = classify_source_quality(ast_record, source_path)
    class_roles = classify_class_roles(ast_record)
    if not source_decision["accepted"]:
        record = _empty_v2_record(source_decision, class_roles, task_text_provenance)
        validate_v2_record(record, catalog)
        return record

    record = compile_source_grounded_record(
        ast_record,
        ordered_steps,
        catalog,
        task_text_provenance=task_text_provenance,
    )
    record["source_quality_decision"] = source_decision
    record["class_role_decisions"] = class_roles
    record["bounded_identity_decisions"] = []
    record["suppressed_evidence"] = []
    record["duplicate_groups"] = []
    record["unresolved_evidence"] = list(record["unsupported_evidence"])
    record["extractor_profile"] = "v2"
    record["extractor_schema_version"] = V2_SCHEMA_VERSION
    _filter_class_identity(record, class_roles)
    _refresh_derived_fields(record)
    validate_v2_record(record, catalog)
    return record
```

Add the validator in the same file:

```python
def validate_v2_record(record: Mapping[str, Any], catalog: Mapping[str, Any]) -> None:
    if record.get("extractor_profile") != "v2":
        raise QgisSourceGroundedV2Error("v2 record has invalid extractor profile")
    if record.get("extractor_schema_version") != V2_SCHEMA_VERSION:
        raise QgisSourceGroundedV2Error("v2 record has invalid schema version")
    decision = record.get("source_quality_decision", {}).get("decision")
    if decision not in SOURCE_DECISIONS:
        raise QgisSourceGroundedV2Error(f"invalid source decision: {decision}")
    for item in record.get("class_role_decisions", []):
        if item.get("role") not in CLASS_ROLES:
            raise QgisSourceGroundedV2Error(f"invalid class role: {item.get('role')}")
    catalog_ids = {str(value).lower() for value in catalog}
    for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence"):
        for item in record.get(key, []):
            operator_id = str(item.get("operator_id") or "").lower()
            if not _PROVIDER_QUALIFIED_ID.fullmatch(operator_id) or operator_id not in catalog_ids:
                raise QgisSourceGroundedV2Error(f"unbounded operator identity: {operator_id}")
            if not item.get("evidence_ids"):
                raise QgisSourceGroundedV2Error(f"operator lacks evidence IDs: {operator_id}")
    if not record.get("source_quality_decision", {}).get("accepted"):
        positive_count = sum(len(record.get(key, [])) for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence"))
        positive_count += len(record.get("custom_components", []))
        if positive_count:
            raise QgisSourceGroundedV2Error("rejected source emitted positive items")
    if record.get("taxonomy_admission") != "not_granted":
        raise QgisSourceGroundedV2Error("v2.1 cannot grant taxonomy admission")
    if record.get("training_admission") != "not_granted" or record.get("training_rows_emitted") != 0:
        raise QgisSourceGroundedV2Error("v2.1 cannot emit training rows")
```

- [ ] **Step 4: Run the v2 compiler tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v2 -v
```

Expected: source rejection and class filtering tests pass.

- [ ] **Step 5: Commit the isolated compiler shell**

```powershell
git add src/gis_recommend/data/qgis_source_grounded_v2.py tests/test_qgis_source_grounded_v2.py
git commit -m "Create an auditable v2 compiler without disturbing v1" -m "The precision gate is implemented as a deterministic post-processing profile over frozen v1 evidence, with source and class decisions retained in every record." -m "Constraint: stable v1 behavior and artifacts remain authoritative" -m "Rejected: Editing v1 rule tables in place | it would make profile regressions hard to attribute" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: source rejection, class filtering and v2 contract"
```

### Task 5: Add Constructor Suppression And Reviewed Identity Corrections

**Files:**
- Modify: `src/gis_recommend/data/qgis_source_grounded_v2.py`
- Modify: `tests/test_qgis_source_grounded_v2.py`

- [ ] **Step 1: Add failing tests for constructor and identity behavior**

Add table-driven cases:

```python
    def test_suppresses_transform_constructor_but_keeps_execution(self):
        result = compile_source_grounded_record_v2(
            {"type": "Module", "body": [{"type": "FunctionDef", "name": "run", "body": []}]},
            [
                {"evidence_id": "ctor", "statement_index": 1, "operation": "QgsCoordinateTransform", "channel": "direct_api"},
                {"evidence_id": "exec", "statement_index": 2, "operation": "QgsCoordinateTransform.transformBoundingBox", "channel": "direct_api"},
            ],
            {"native:reprojectlayer": {}},
            source_path="gps_importer.py",
        )

        self.assertEqual(result["operator_chain"], ["native:reprojectlayer"])
        self.assertEqual(result["suppressed_evidence"][0]["evidence_id"], "ctor")
        self.assertEqual(result["suppressed_evidence"][0]["reason"], "constructor_or_configuration")

    def test_resolves_reviewed_direct_api_identity_gaps(self):
        cases = [
            ("gdal.ComputeProximity", "gdal:proximity"),
            ("gdal_merge.main", "gdal:merge"),
            ("sampled.selectByExpression", "native:extractbyexpression"),
            ("QgsVectorFileWriter.writeAsVectorFormat", "native:savefeatures"),
            ("shapely.ops.polygonize", "native:polygonize"),
        ]
        catalog = {operator_id: {} for _operation, operator_id in cases}
        for operation, expected in cases:
            with self.subTest(operation=operation):
                result = compile_source_grounded_record_v2(
                    {"type": "Module", "body": [{"type": "FunctionDef", "name": "run", "body": []}]},
                    [{"evidence_id": operation, "statement_index": 1, "operation": operation, "channel": "direct_api"}],
                    catalog,
                    source_path="workflow.py",
                )
                self.assertEqual(result["operator_chain"], [expected])

    def test_preserves_explicit_raster_sampling(self):
        result = compile_source_grounded_record_v2(
            {"type": "Module", "body": [{"type": "FunctionDef", "name": "run", "body": []}]},
            [{"evidence_id": "sampling", "operation": "processing.run:qgis:rastersampling", "channel": "direct_api"}],
            {"qgis:rastersampling": {}},
            source_path="sampling.py",
        )
        self.assertEqual(result["operator_chain"], ["qgis:rastersampling"])

    def test_keeps_raster_polygonize_distinct_from_shapely_polygonize(self):
        catalog = {"gdal:polygonize": {}, "native:polygonize": {}}
        steps = [
            {"evidence_id": "raster", "statement_index": 1, "operation": "gdal.Polygonize", "channel": "direct_api"},
            {"evidence_id": "lines", "statement_index": 2, "operation": "shapely.ops.polygonize", "channel": "direct_api"},
        ]
        result = compile_source_grounded_record_v2(
            {"type": "Module", "body": [{"type": "FunctionDef", "name": "run", "body": []}]},
            steps,
            catalog,
            source_path="polygonize.py",
        )
        self.assertEqual(result["operator_chain"], ["gdal:polygonize", "native:polygonize"])
```

- [ ] **Step 2: Run the new tests and verify the current v2 shell fails**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_suppresses_transform_constructor_but_keeps_execution tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_resolves_reviewed_direct_api_identity_gaps tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_preserves_explicit_raster_sampling tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_keeps_raster_polygonize_distinct_from_shapely_polygonize -v
```

Expected: failures showing the constructor is still emitted and reviewed gaps remain absent or misidentified.

- [ ] **Step 3: Add exact v2 suppression and identity tables**

Add these tables and resolver functions:

```python
from gis_recommend.data.qgis_pilot import normalize_qgis_operation


_CONSTRUCTOR_OR_CONFIGURATION = {
    "qgscoordinatetransform",
    "qgsprocessingparametervectorlayer",
    "qgsprocessingparameterrasterlayer",
    "qgsprocessingparameterfeaturesource",
    "qgsprocessingparameterfeaturedestination",
    "gdal.warpoptions",
    "gdal.translateoptions",
    "gdal.rasterizeoptions",
    "qgsprocessingregistry",
}

_V2_DIRECT_IDENTITIES = (
    (("qgscoordinatetransform.transform", "qgscoordinatetransform.transformboundingbox", "qgsgeometry.transform"), ("native:reprojectlayer", "qgis:reprojectlayer"), "crs_transform"),
    (("gdal.computeproximity",), ("gdal:proximity",), "proximity"),
    (("gdal_merge.main",), ("gdal:merge",), "raster_merge"),
    (("sampled.selectbyexpression", "qgsvectorlayer.selectbyexpression", "qgsfeaturerequest.setfilterexpression"), ("native:extractbyexpression",), "attribute_filter"),
    (("qgsvectorfilewriter.writeasvectorformat", "qgsvectorfilewriter.writeasvectorformatv2", "qgsvectorfilewriter.writeasvectorformatv3"), ("native:savefeatures",), "data_export"),
    (("shapely.ops.polygonize",), ("native:polygonize",), "line_polygonize"),
    (("gdal.polygonize",), ("gdal:polygonize",), "raster_polygonize"),
)


def _evidence_step_index(ordered_steps):
    index = {}
    for ordinal, raw_step in enumerate(ordered_steps):
        step = dict(raw_step)
        evidence_id = str(step.get("evidence_id") or step.get("step_id") or f"ordered-step-{ordinal + 1}")
        index[evidence_id] = step
    return index


def _resolve_exact_v2_identity(operation, catalog_ids):
    normalized = normalize_qgis_operation(operation)
    if normalized.startswith("processing.run:"):
        normalized = normalized[len("processing.run:"):]
    if _PROVIDER_QUALIFIED_ID.fullmatch(normalized):
        return (normalized, "explicit_processing") if normalized in catalog_ids else (None, None)
    for patterns, candidates, family in _V2_DIRECT_IDENTITIES:
        if not any(normalized == pattern or normalized.startswith(f"{pattern}.") for pattern in patterns):
            continue
        present = [operator_id for operator_id in candidates if operator_id in catalog_ids]
        return (present[0], family) if len(present) == 1 else (None, family)
    return None, None


def _suppress_constructor_evidence(record, step_index):
    for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence"):
        kept = []
        for item in record[key]:
            evidence_ids = item.get("evidence_ids") or []
            steps = [step_index[value] for value in evidence_ids if value in step_index]
            operations = [normalize_qgis_operation(step.get("operation")) for step in steps]
            if operations and all(operation in _CONSTRUCTOR_OR_CONFIGURATION for operation in operations):
                record["suppressed_evidence"].append(
                    {
                        "evidence_id": evidence_ids[0],
                        "operator_id": item["operator_id"],
                        "operation": operations[0],
                        "reason": "constructor_or_configuration",
                    }
                )
            else:
                kept.append(item)
        record[key] = kept


def _promote_or_correct_reviewed_identities(record, ordered_steps, catalog):
    catalog_ids = {str(value).lower() for value in catalog}
    step_index = _evidence_step_index(ordered_steps)
    evidence_by_id = {
        evidence_id: item
        for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence")
        for item in record[key]
        for evidence_id in item.get("evidence_ids") or []
    }
    for evidence_id, step in step_index.items():
        operator_id, family = _resolve_exact_v2_identity(step.get("operation"), catalog_ids)
        if operator_id is None:
            continue
        existing = evidence_by_id.get(evidence_id)
        if existing is not None:
            if existing["operator_id"] != operator_id:
                record["bounded_identity_decisions"].append(
                    {
                        "evidence_id": evidence_id,
                        "from_operator_id": existing["operator_id"],
                        "to_operator_id": operator_id,
                        "reason": "reviewed_exact_identity_correction",
                    }
                )
                existing["operator_id"] = operator_id
                existing["semantic_family"] = family
            continue
        record["operator_evidence"].append(
            {
                "operator_id": operator_id,
                "evidence_tier": "E0" if family == "explicit_processing" else "E2",
                "evidence_ids": [evidence_id],
                "statement_index": step.get("statement_index"),
                "source_line": step.get("source_line") or step.get("lineno") or step.get("line"),
                "semantic_step_id": step.get("semantic_step_id"),
                "semantic_family": family,
                "confidence": 1.0 if family == "explicit_processing" else 0.9,
                "arguments": step.get("args", step.get("arguments", [])),
                "input_roles": step.get("input_roles", []),
                "output_roles": step.get("output_roles", []),
                "dependencies": step.get("dependencies", []),
                "scope": step.get("scope"),
            }
        )
        record["bounded_identity_decisions"].append(
            {
                "evidence_id": evidence_id,
                "from_operator_id": None,
                "to_operator_id": operator_id,
                "reason": "reviewed_exact_identity_promotion",
            }
        )
```

Call `_suppress_constructor_evidence()` before `_promote_or_correct_reviewed_identities()`, then sort `operator_evidence` by numeric `statement_index`, source line and original insertion order before refreshing derived fields.

- [ ] **Step 4: Run the identity and constructor tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v2 -v
```

Expected: all v2 tests pass, and v1 compatibility tests remain green.

- [ ] **Step 5: Commit reviewed identity behavior**

```powershell
git add src/gis_recommend/data/qgis_source_grounded_v2.py tests/test_qgis_source_grounded_v2.py
git commit -m "Correct reviewed QGIS identities without admitting constructors" -m "The locked review established exact provider identities for proximity, merge, expression filtering, export and line polygonization, while configuration objects must remain audit-only." -m "Constraint: ambiguous provider candidates must abstain" -m "Rejected: suffix-only operator matching | raster and line polygonize are semantically distinct" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: constructor suppression and seven reviewed identity families"
```

### Task 6: Add Bounded Class Identity Precedence And Semantic Deduplication

**Files:**
- Modify: `src/gis_recommend/data/qgis_source_grounded_v2.py`
- Modify: `tests/test_qgis_source_grounded_v2.py`

- [ ] **Step 1: Add failing legacy Eliminate precedence test**

```python
    def test_legacy_eliminate_identity_suppresses_internal_overlay_steps(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "Eliminate",
                    "bases": [{"type": "Name", "id": "GeoAlgorithm"}],
                    "body": [
                        {"type": "FunctionDef", "name": "defineCharacteristics", "body": []},
                        {"type": "FunctionDef", "name": "processAlgorithm", "body": []},
                    ],
                }
            ],
        }
        steps = [
            {"evidence_id": "intersect", "statement_index": 1, "operation": "QgsGeometry.intersection", "channel": "direct_api"},
            {"evidence_id": "combine", "statement_index": 2, "operation": "QgsGeometry.combine", "channel": "direct_api"},
        ]
        result = compile_source_grounded_record_v2(
            ast_record,
            steps,
            {
                "qgis:eliminateselectedpolygons": {},
                "native:intersection": {},
                "native:union": {},
            },
            source_path="Eliminate.py",
        )

        self.assertEqual(result["operator_chain"], ["qgis:eliminateselectedpolygons"])
        self.assertEqual(
            {item["reason"] for item in result["suppressed_evidence"]},
            {"bounded_class_implementation_substep"},
        )

    def test_self_describing_class_marks_scoped_e2_as_implementation_substep(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [{"type": "Name", "id": "QgisAlgorithm"}],
                    "body": [
                        {
                            "type": "FunctionDef",
                            "name": "name",
                            "body": [
                                {
                                    "type": "Return",
                                    "value": {"type": "Constant", "value": "convertgeometrytype"},
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        result = compile_source_grounded_record_v2(
            ast_record,
            [
                {
                    "evidence_id": "centroid",
                    "operation": "QgsGeometry.centroid",
                    "channel": "direct_api",
                    "scope": "GeometryConvert.processAlgorithm",
                }
            ],
            {"qgis:convertgeometrytype": {}, "native:centroids": {}},
            source_path="geometry_convert.py",
        )

        self.assertEqual(result["operator_chain"], ["qgis:convertgeometrytype"])
        self.assertEqual(result["supporting_operator_chain"], ["native:centroids"])
        self.assertEqual(
            result["supporting_operator_evidence"][0]["evidence_role"],
            "implementation_substep",
        )
```

- [ ] **Step 2: Add failing semantic duplicate tests**

```python
    def test_merges_same_input_output_buildvrt_but_preserves_distinct_output(self):
        steps = [
            {
                "evidence_id": "macro-vrt-a",
                "statement_index": 1,
                "operation": "gdal.BuildVRT",
                "channel": "direct_api",
                "input_roles": ["band_1", "band_2"],
                "output_roles": ["stack.vrt"],
            },
            {
                "evidence_id": "micro-vrt-a",
                "statement_index": 2,
                "operation": "gdal.BuildVRT",
                "channel": "direct_api",
                "input_roles": ["band_1", "band_2"],
                "output_roles": ["stack.vrt"],
            },
            {
                "evidence_id": "vrt-b",
                "statement_index": 3,
                "operation": "gdal.BuildVRT",
                "channel": "direct_api",
                "input_roles": ["band_1", "band_2"],
                "output_roles": ["preview.vrt"],
            },
        ]
        result = compile_source_grounded_record_v2(
            {"type": "Module", "body": [{"type": "FunctionDef", "name": "run", "body": []}]},
            steps,
            {"gdal:buildvirtualraster": {}},
            source_path="vrt.py",
        )

        self.assertEqual(result["operator_chain"], ["gdal:buildvirtualraster", "gdal:buildvirtualraster"])
        self.assertEqual(result["duplicate_groups"][0]["member_evidence_ids"], ["macro-vrt-a", "micro-vrt-a"])
```

- [ ] **Step 3: Run the precedence and duplicate tests before implementation**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_legacy_eliminate_identity_suppresses_internal_overlay_steps tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_self_describing_class_marks_scoped_e2_as_implementation_substep tests.test_qgis_source_grounded_v2.QgisSourceGroundedV2Tests.test_merges_same_input_output_buildvrt_but_preserves_distinct_output -v
```

Expected: Eliminate remains E3 with leaked E2 substeps, scoped E2 lacks the implementation marker, and duplicate BuildVRT remains over-counted.

- [ ] **Step 4: Implement exact legacy class identity and internal-step policy**

```python
_LEGACY_CLASS_IDENTITIES = (
    {
        "class_name": "Eliminate",
        "required_base_suffix": "geoalgorithm",
        "required_methods": {"defineCharacteristics", "processAlgorithm"},
        "operator_id": "qgis:eliminateselectedpolygons",
        "suppress_internal_families": {"intersection", "union"},
    },
)


def _method_names(class_node):
    return {
        str(item.get("name") or "")
        for item in class_node.get("body") or []
        if isinstance(item, Mapping) and str(item.get("type") or item.get("_type") or "") in {"FunctionDef", "AsyncFunctionDef"}
    }


def _walk_ast_mappings(value):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_ast_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_ast_mappings(child)


def _class_bases(class_node):
    values = []
    for base in class_node.get("bases") or []:
        if isinstance(base, Mapping) and str(base.get("type") or base.get("_type") or "") == "Name":
            values.append(str(base.get("id") or "").lower())
    return values


def _apply_legacy_class_identity(record, ast_record, catalog):
    catalog_ids = {str(value).lower() for value in catalog}
    for node in _walk_ast_mappings(ast_record):
        if str(node.get("type") or node.get("_type") or "") != "ClassDef":
            continue
        for rule in _LEGACY_CLASS_IDENTITIES:
            if str(node.get("name") or "") != rule["class_name"]:
                continue
            if rule["operator_id"] not in catalog_ids:
                continue
            if not any(base.endswith(rule["required_base_suffix"]) for base in _class_bases(node)):
                continue
            if not rule["required_methods"].issubset(_method_names(node)):
                continue
            record["custom_components"] = [item for item in record["custom_components"] if item["class_name"] != rule["class_name"]]
            record["operator_evidence"].insert(
                0,
                {
                    "operator_id": rule["operator_id"],
                    "evidence_tier": "E1",
                    "evidence_ids": [f"bounded-class:{rule['class_name']}"],
                    "line": node.get("lineno"),
                    "source_ordinal": 0,
                    "semantic_family": "bounded_legacy_class",
                    "confidence": 1.0,
                    "arguments": [],
                    "input_roles": [],
                    "output_roles": [],
                    "dependencies": [],
                    "scope": rule["class_name"],
                },
            )
            kept = []
            for item in record["operator_evidence"][1:]:
                if item.get("semantic_family") in rule["suppress_internal_families"]:
                    record["suppressed_evidence"].append(
                        {
                            "evidence_id": item["evidence_ids"][0],
                            "operator_id": item["operator_id"],
                            "reason": "bounded_class_implementation_substep",
                            "bounded_operator_id": rule["operator_id"],
                        }
                    )
                else:
                    kept.append(item)
            record["operator_evidence"] = [record["operator_evidence"][0], *kept]
            record["bounded_identity_decisions"].append(
                {
                    "class_name": rule["class_name"],
                    "operator_id": rule["operator_id"],
                    "reason": "reviewed_legacy_class_signature",
                }
            )


def _mark_scoped_e1_implementation_substeps(record):
    accepted_classes = {
        str(item["class_name"]).lower()
        for item in record.get("class_operators", [])
    }
    for item in record.get("supporting_operator_evidence", []):
        if item.get("evidence_tier") != "E2":
            continue
        scope = str(item.get("scope") or "").lower()
        owner = next(
            (class_name for class_name in accepted_classes if class_name in scope),
            None,
        )
        if owner is None:
            continue
        item["evidence_role"] = "implementation_substep"
        record["suppressed_evidence"].append(
            {
                "evidence_id": item["evidence_ids"][0],
                "operator_id": item["operator_id"],
                "reason": "bounded_class_implementation_substep",
                "bounded_class_name": owner,
                "retained_as_supporting_evidence": True,
            }
        )
```

The rule is class-signature based and must not inspect record IDs or review order.

- [ ] **Step 5: Implement conservative semantic-step fingerprints and duplicate groups**

```python
import json


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _semantic_fingerprint(item):
    semantic_step_id = str(item.get("semantic_step_id") or "")
    if semantic_step_id:
        return ("semantic_step_id", item["operator_id"], semantic_step_id)
    input_identity = _canonical(item.get("input_roles") or [])
    output_identity = _canonical(item.get("output_roles") or [])
    if output_identity != "[]":
        return (
            "io_identity",
            item["operator_id"],
            input_identity,
            output_identity,
            str(item.get("scope") or ""),
            _canonical(item.get("dependencies") or []),
        )
    return None


def _merge_semantic_duplicates(record):
    groups = {}
    kept = []
    for item in record["operator_evidence"]:
        fingerprint = _semantic_fingerprint(item)
        if fingerprint is None or fingerprint not in groups:
            kept.append(item)
            if fingerprint is not None:
                groups[fingerprint] = item
            continue
        keeper = groups[fingerprint]
        merged_ids = list(item.get("evidence_ids") or [])
        keeper["evidence_ids"].extend(value for value in merged_ids if value not in keeper["evidence_ids"])
        record["duplicate_groups"].append(
            {
                "operator_id": item["operator_id"],
                "fingerprint_kind": fingerprint[0],
                "keeper_evidence_id": keeper["evidence_ids"][0],
                "member_evidence_ids": [keeper["evidence_ids"][0], *merged_ids],
                "reason": "same_semantic_step",
            }
        )
    record["operator_evidence"] = kept
```

Call order inside `compile_source_grounded_record_v2()` must be:

1. source gate
2. v1 compilation
3. class-role filtering
4. constructor suppression
5. reviewed direct identity promotion/correction
6. bounded class identity and implementation-substep suppression
7. scoped E1 implementation-substep marking
8. semantic duplicate merge
9. derived-field refresh
10. contract validation

- [ ] **Step 6: Extend contract validation for duplicate groups**

Add this validation to `validate_v2_record()`:

```python
    evidence_by_id = {
        evidence_id: item
        for key in ("operator_evidence", "parallel_ast_operator_evidence", "supporting_operator_evidence")
        for item in record.get(key, [])
        for evidence_id in item.get("evidence_ids") or []
    }
    for group in record.get("duplicate_groups", []):
        members = list(dict.fromkeys(group.get("member_evidence_ids") or []))
        keeper_id = str(group.get("keeper_evidence_id") or "")
        if len(members) < 2:
            raise QgisSourceGroundedV2Error("duplicate group needs at least two evidence IDs")
        if keeper_id not in members or keeper_id not in evidence_by_id:
            raise QgisSourceGroundedV2Error("duplicate group keeper is not retained")
        if evidence_by_id[keeper_id]["operator_id"] != group.get("operator_id"):
            raise QgisSourceGroundedV2Error("duplicate group operator does not match keeper")
```

- [ ] **Step 7: Run all v2 and v1 compatibility tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v1_compat tests.test_qgis_source_grounded_v2 -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit precedence and deduplication**

```powershell
git add src/gis_recommend/data/qgis_source_grounded_v2.py tests/test_qgis_source_grounded_v2.py
git commit -m "Prefer bounded workflows and merge only identical semantic steps" -m "High-level reviewed class identity now suppresses internal overlay implementation details, while duplicate merging requires shared semantic or output identity." -m "Constraint: repeated operations producing different products must remain distinct" -m "Rejected: operator-ID-only deduplication | it destroys valid repeated workflow steps" -m "Confidence: medium" -m "Scope-risk: moderate" -m "Tested: legacy Eliminate precedence and BuildVRT duplicate boundaries"
```

### Task 7: Add CLI Profile Isolation And v2 Audit Output

**Files:**
- Modify: `scripts/run_qgis_source_grounded_extractor.py`
- Modify: `tests/test_qgis_source_grounded_cli.py`

- [ ] **Step 1: Add failing CLI profile tests**

Add this fixture builder near the existing test helpers:

```python
def _prepare_profile_fixture(root, *, ast_record=None, source_script="workflow.py"):
    source_dir = root / "source"
    source_dir.mkdir()
    ast_path = source_dir / "record_ast.json"
    steps_path = source_dir / "record_steps.csv"
    _write_json(ast_path, ast_record or _processing_ast("native:buffer"))
    with steps_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "statement_index",
                "normalized_api_name",
                "api_source_type",
                "scope",
            ],
            lineterminator="\n",
        )
        writer.writeheader()

    selection_path = root / "selection.jsonl"
    review_path = root / "review.csv"
    catalog_path = root / "catalog.json"
    _write_jsonl(
        selection_path,
        [
            {
                "record_id": "profile-1",
                "source_script": source_script,
                "task_name": "Profile task",
                "task_description": "Profile description",
                "artifact_hashes": {
                    "ast_paths": [str(ast_path)],
                    "ast_hashes": [_sha256(ast_path)],
                    "steps_paths": [str(steps_path)],
                    "steps_hashes": [_sha256(steps_path)],
                },
            }
        ],
    )
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["review_order", "record_id", "candidate_status"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "review_order": 1,
                "record_id": "profile-1",
                "candidate_status": "candidate",
            }
        )
    _write_json(catalog_path, {"native:buffer": {}, "native:union": {}})
    return [
        "--selection-jsonl",
        selection_path,
        "--review-csv",
        review_path,
        "--catalog",
        catalog_path,
        "--allowed-read-root",
        root,
        "--allowed-output-root",
        root,
        "--blind-mode",
    ]
```

Extend the existing CLI test class with:

```python
    def test_help_exposes_v1_v2_profile_and_defaults_to_v1(self):
        result = self._run("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--extractor-profile {v1,v2}", result.stdout)

    def test_v2_record_contains_profile_schema_and_audit_fields(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "v2-output"
            common = _prepare_profile_fixture(
                root,
                source_script="tests/test_geometry.py",
                ast_record={
                    "type": "Module",
                    "body": [
                        {
                            "type": "ClassDef",
                            "name": "TestGeometry",
                            "bases": [{"type": "Name", "id": "unittest.TestCase"}],
                            "body": [
                                {"type": "FunctionDef", "name": "test_union", "body": []},
                                {"type": "FunctionDef", "name": "test_difference", "body": []},
                            ],
                        }
                    ],
                },
            )
            result = self._run(*common, "--extractor-profile", "v2", "--output-dir", output_dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            extraction = json.loads((output_dir / "extractions.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(extraction["extractor_profile"], "v2")
            self.assertEqual(extraction["extractor_schema_version"], "qgis_source_grounded_extraction_v2_1")
            self.assertEqual(extraction["operator_chain"], [])
            self.assertIn("source_quality_decision", extraction)
            self.assertIn("class_role_decisions", extraction)

    def test_default_profile_and_explicit_v1_write_identical_semantic_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            default_dir = root / "default-output"
            explicit_dir = root / "explicit-output"
            common = _prepare_profile_fixture(root)
            default_result = self._run(*common, "--output-dir", default_dir)
            explicit_result = self._run(*common, "--extractor-profile", "v1", "--output-dir", explicit_dir)
            self.assertEqual(default_result.returncode, 0, default_result.stderr)
            self.assertEqual(explicit_result.returncode, 0, explicit_result.stderr)
            self.assertEqual(
                (default_dir / "extractions.jsonl").read_text(encoding="utf-8"),
                (explicit_dir / "extractions.jsonl").read_text(encoding="utf-8"),
            )
```

- [ ] **Step 2: Run the new CLI tests and verify profile support is absent**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_cli.QgisSourceGroundedCliTests.test_help_exposes_v1_v2_profile_and_defaults_to_v1 tests.test_qgis_source_grounded_cli.QgisSourceGroundedCliTests.test_v2_record_contains_profile_schema_and_audit_fields tests.test_qgis_source_grounded_cli.QgisSourceGroundedCliTests.test_default_profile_and_explicit_v1_write_identical_semantic_outputs -v
```

Expected: failures for missing parser option and v2 metadata.

- [ ] **Step 3: Add profile parsing and compiler dispatch**

At module imports:

```python
from gis_recommend.data.qgis_source_grounded_v2 import (
    QgisSourceGroundedV2Error,
    V2_SCHEMA_VERSION,
    compile_source_grounded_record_v2,
)
```

In `_build_parser()`:

```python
parser.add_argument(
    "--extractor-profile",
    choices=("v1", "v2"),
    default="v1",
    help="Extractor behavior profile; v1 remains the stable default.",
)
```

Replace the compilation call with:

```python
task_text_provenance = {
    "source": "selection_jsonl",
    "task_name_present": bool(selection.get("task_name")),
    "task_description_present": bool(selection.get("task_description")),
}
if args.extractor_profile == "v2":
    extracted = compile_source_grounded_record_v2(
        ast_record,
        ordered_steps,
        catalog,
        source_path=str(selection.get("source_script") or ""),
        task_text_provenance=task_text_provenance,
    )
    extraction_schema = V2_SCHEMA_VERSION
else:
    extracted = compile_source_grounded_record(
        ast_record,
        ordered_steps,
        catalog,
        task_text_provenance=task_text_provenance,
    )
    extraction_schema = "qgis_source_grounded_extraction_v1"
    extracted["extractor_profile"] = "v1"
    extracted["extractor_schema_version"] = extraction_schema
```

Build every extraction with:

```python
{
    "schema_version": extraction_schema,
    "extractor_profile": args.extractor_profile,
    "extractor_schema_version": extraction_schema,
    "review_order": review_order,
    "record_id": str(selection.get("record_id")),
    "source_script": selection.get("source_script"),
    "task_name": selection.get("task_name"),
    "task_description": selection.get("task_description"),
    "candidate_status": review.get("candidate_status"),
    "source_artifacts": source_ledger,
    **extracted,
}
```

Add profile metadata to the summary immediately after the summary dictionary is built:

```python
summary["extractor_profile"] = args.extractor_profile
summary["extractor_schema_version"] = extraction_schema
```

Build the ledger code-hash map with:

```python
extractor_code = {
    "cli_sha256": _sha256(Path(__file__).resolve()),
    "v1_module_sha256": _sha256(
        SRC / "gis_recommend" / "data" / "qgis_source_grounded_extractor.py"
    ),
}
if args.extractor_profile == "v2":
    extractor_code.update(
        {
            "v2_module_sha256": _sha256(
                SRC / "gis_recommend" / "data" / "qgis_source_grounded_v2.py"
            ),
            "source_quality_module_sha256": _sha256(
                SRC / "gis_recommend" / "data" / "qgis_source_quality.py"
            ),
        }
    )
```

Use it in the ledger:

```python
"extractor_profile": args.extractor_profile,
"extractor_schema_version": extraction_schema,
"extractor_code": extractor_code,
```

Replace the exception tuple with:

```python
except (
    ExtractorCliError,
    QgisSourceGroundedV2Error,
    OSError,
    ValueError,
    json.JSONDecodeError,
) as error:
    print(f"error: {error}", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Extend review CSV fields for v2 audits**

Append these columns to `_write_review_csv()` fieldnames:

```python
"extractor_profile",
"extractor_schema_version",
"source_quality_decision_json",
"class_role_decisions_json",
"bounded_identity_decisions_json",
"suppressed_evidence_json",
"duplicate_groups_json",
"unresolved_evidence_count",
```

Populate them for every row, using empty v1 defaults:

```python
"extractor_profile": row.get("extractor_profile", "v1"),
"extractor_schema_version": row.get(
    "extractor_schema_version", "qgis_source_grounded_extraction_v1"
),
"source_quality_decision_json": _canonical_json(
    row.get("source_quality_decision", {})
),
"class_role_decisions_json": _canonical_json(
    row.get("class_role_decisions", [])
),
"bounded_identity_decisions_json": _canonical_json(
    row.get("bounded_identity_decisions", [])
),
"suppressed_evidence_json": _canonical_json(
    row.get("suppressed_evidence", [])
),
"duplicate_groups_json": _canonical_json(row.get("duplicate_groups", [])),
"unresolved_evidence_count": len(row.get("unresolved_evidence", [])),
```

Keep all existing v1 workbook columns so downstream review readers remain compatible.

- [ ] **Step 5: Run CLI and focused extractor suites**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_cli tests.test_qgis_source_grounded_v1_compat tests.test_qgis_source_grounded_extractor tests.test_qgis_source_grounded_semantic_compiler tests.test_qgis_source_grounded_v2 -v
```

Expected: all focused tests pass; omitted profile and explicit `v1` produce identical extraction JSONL.

- [ ] **Step 6: Commit profile isolation**

```powershell
git add scripts/run_qgis_source_grounded_extractor.py tests/test_qgis_source_grounded_cli.py
git commit -m "Expose extractor v2 only through an explicit audited profile" -m "The CLI now isolates v2 schema, code hashes and review fields while preserving v1 as the default execution path." -m "Constraint: v2 artifacts must never overwrite frozen v1 reports" -m "Confidence: high" -m "Scope-risk: moderate" -m "Directive: Do not change the profile default before a new blind gate passes" -m "Tested: default/explicit v1 parity and v2 CLI artifact contract"
```

### Task 8: Implement The Locked v2.1 Precision Gate Evaluator

**Files:**
- Create: `src/gis_recommend/data/qgis_source_grounded_gate.py`
- Create: `tests/test_qgis_source_grounded_gate.py`
- Modify: `scripts/run_qgis_source_grounded_extractor.py`
- Modify: `tests/test_qgis_source_grounded_cli.py`

- [ ] **Step 1: Write failing gold-multiset and metric tests**

```python
import unittest

from gis_recommend.data.qgis_source_grounded_gate import evaluate_v2_1_gate


class QgisSourceGroundedGateTests(unittest.TestCase):
    def test_counts_reviewed_duplicates_and_missing_expected_ids(self):
        adjudication = {
            "record_id": "r1",
            "expected_operator_ids": ["gdal:buildvirtualraster", "gdal:merge"],
            "expected_custom_components": [],
            "operator_item_verdicts": [
                {"operator_id": "gdal:buildvirtualraster", "occurrence": 1, "correct": True, "evidence_tier": "E2"},
                {"operator_id": "gdal:buildvirtualraster", "occurrence": 2, "correct": True, "evidence_tier": "E2"},
            ],
            "failure_tags": ["bounded_operator_omission:gdal:merge"],
        }
        extraction = {
            "record_id": "r1",
            "operator_evidence": [
                {"operator_id": "gdal:buildvirtualraster", "evidence_tier": "E2", "evidence_ids": ["a"]},
                {"operator_id": "gdal:buildvirtualraster", "evidence_tier": "E2", "evidence_ids": ["b"]},
                {"operator_id": "gdal:merge", "evidence_tier": "E2", "evidence_ids": ["c"]},
            ],
            "custom_components": [],
            "source_quality_decision": {"decision": "accepted_workflow", "accepted": True},
            "suppressed_evidence": [],
        }

        summary, rows = evaluate_v2_1_gate([extraction], [adjudication])

        self.assertEqual(summary["overall_item_correct"], 3)
        self.assertEqual(summary["overall_item_predicted"], 3)
        self.assertEqual(summary["complete_records"], 1)
        self.assertEqual(rows[0]["missing_gold_items"], [])

    def test_counts_test_and_constructor_false_positives(self):
        adjudications = [
            {"record_id": "test", "expected_operator_ids": [], "expected_custom_components": [], "operator_item_verdicts": [], "failure_tags": ["test_source_not_filtered"]},
            {"record_id": "transform", "expected_operator_ids": ["native:reprojectlayer"], "expected_custom_components": [], "operator_item_verdicts": [{"operator_id": "native:reprojectlayer", "occurrence": 1, "correct": False, "evidence_tier": "E2"}, {"operator_id": "native:reprojectlayer", "occurrence": 2, "correct": True, "evidence_tier": "E2"}], "failure_tags": ["transform_constructor_false_positive"]},
        ]
        extractions = [
            {"record_id": "test", "operator_evidence": [{"operator_id": "native:union", "evidence_tier": "E2", "evidence_ids": ["u"]}], "custom_components": [], "source_quality_decision": {"decision": "accepted_workflow", "accepted": True}, "suppressed_evidence": []},
            {"record_id": "transform", "operator_evidence": [{"operator_id": "native:reprojectlayer", "evidence_tier": "E2", "evidence_ids": ["exec"]}, {"operator_id": "native:reprojectlayer", "evidence_tier": "E2", "evidence_ids": ["ctor"]}], "custom_components": [], "source_quality_decision": {"decision": "accepted_workflow", "accepted": True}, "suppressed_evidence": []},
        ]

        summary, _rows = evaluate_v2_1_gate(extractions, adjudications)

        self.assertEqual(summary["test_source_false_positives"], 1)
        self.assertEqual(summary["constructor_false_positives"], 1)
        self.assertFalse(summary["hard_gate_passed"])

    def test_bounded_class_upgrade_does_not_require_obsolete_e3_fallback(self):
        adjudication = {
            "record_id": "eliminate",
            "expected_operator_ids": ["qgis:eliminateselectedpolygons"],
            "expected_custom_components": ["Eliminate"],
            "operator_item_verdicts": [],
            "custom_item_verdicts": [
                {
                    "class_name": "Eliminate",
                    "correct": True,
                    "evidence_tier": "E3",
                    "reason": "real_processing_algorithm_class_but_bounded_identity_missed",
                }
            ],
            "failure_tags": ["class_identity_not_resolved"],
        }
        extraction = {
            "record_id": "eliminate",
            "operator_evidence": [
                {
                    "operator_id": "qgis:eliminateselectedpolygons",
                    "evidence_tier": "E1",
                    "evidence_ids": ["bounded-class:Eliminate"],
                }
            ],
            "custom_components": [],
            "source_quality_decision": {"decision": "accepted_workflow", "accepted": True},
            "suppressed_evidence": [],
        }

        summary, rows = evaluate_v2_1_gate([extraction], [adjudication])

        self.assertEqual(rows[0]["missing_gold_items"], [])
        self.assertEqual(summary["complete_records"], 1)
```

- [ ] **Step 2: Run the gate tests and verify the module is missing**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_gate -v
```

Expected: import failure for `qgis_source_grounded_gate`.

- [ ] **Step 3: Implement deterministic gold construction and matching**

```python
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


V2_1_THRESHOLDS = {
    "E0": 0.80,
    "E2": 0.85,
    "E3": 0.70,
    "overall": 0.80,
    "complete_rate": 0.257,
}


def _gold_operator_counter(adjudication: Mapping[str, Any]) -> Counter:
    correct = Counter(
        str(item["operator_id"])
        for item in adjudication.get("operator_item_verdicts", [])
        if item.get("correct") is True
    )
    for operator_id in adjudication.get("expected_operator_ids", []):
        operator_id = str(operator_id)
        if correct[operator_id] == 0:
            correct[operator_id] = 1
    return correct


def _gold_custom_counter(adjudication: Mapping[str, Any]) -> Counter:
    bounded_fallbacks = {
        str(item.get("class_name") or "")
        for item in adjudication.get("custom_item_verdicts", [])
        if item.get("correct") is True
        and "bounded_identity_missed" in str(item.get("reason") or "")
    }
    return Counter(
        str(value)
        for value in adjudication.get("expected_custom_components", [])
        if str(value) not in bounded_fallbacks
    )


def _predicted_items(extraction: Mapping[str, Any]) -> list[dict[str, str]]:
    items = [
        {"identity": str(item["operator_id"]), "evidence_tier": str(item["evidence_tier"]), "kind": "operator"}
        for item in extraction.get("operator_evidence", [])
    ]
    items.extend(
        {"identity": str(item["class_name"]), "evidence_tier": "E3", "kind": "custom"}
        for item in extraction.get("custom_components", [])
    )
    return items


def evaluate_v2_1_gate(
    extractions: list[Mapping[str, Any]],
    adjudications: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    extraction_ids = [str(item["record_id"]) for item in extractions]
    adjudication_ids = [str(item["record_id"]) for item in adjudications]
    if len(extraction_ids) != len(set(extraction_ids)):
        raise ValueError("duplicate extraction record IDs")
    if len(adjudication_ids) != len(set(adjudication_ids)):
        raise ValueError("duplicate adjudication record IDs")
    if set(extraction_ids) != set(adjudication_ids):
        raise ValueError("extraction and adjudication record IDs differ")
    adjudication_by_id = {str(item["record_id"]): item for item in adjudications}
    tier_predicted = Counter()
    tier_correct = Counter()
    overall_predicted = 0
    overall_correct = 0
    complete_records = 0
    test_false_positives = 0
    constructor_false_positives = 0
    rows = []

    for extraction in extractions:
        record_id = str(extraction["record_id"])
        adjudication = adjudication_by_id[record_id]
        gold_operators = _gold_operator_counter(adjudication)
        gold_custom = _gold_custom_counter(adjudication)
        remaining_operators = gold_operators.copy()
        remaining_custom = gold_custom.copy()
        predicted = _predicted_items(extraction)
        matched = []
        false_positive = []
        for item in predicted:
            target = remaining_operators if item["kind"] == "operator" else remaining_custom
            correct = target[item["identity"]] > 0
            if correct:
                target[item["identity"]] -= 1
                matched.append(item)
            else:
                false_positive.append(item)
            tier_predicted[item["evidence_tier"]] += 1
            tier_correct[item["evidence_tier"]] += int(correct)
            overall_predicted += 1
            overall_correct += int(correct)

        missing = [
            {"identity": identity, "kind": kind}
            for kind, counter in (("operator", remaining_operators), ("custom", remaining_custom))
            for identity, count in counter.items()
            for _ in range(count)
        ]
        complete = not false_positive and not missing
        complete_records += int(complete)
        failure_tags = set(str(value) for value in adjudication.get("failure_tags", []))
        if "test_source_not_filtered" in failure_tags and predicted:
            test_false_positives += len(predicted)
        if "transform_constructor_false_positive" in failure_tags:
            expected_reprojects = gold_operators["native:reprojectlayer"]
            predicted_reprojects = sum(item["identity"] == "native:reprojectlayer" for item in predicted)
            constructor_false_positives += max(0, predicted_reprojects - expected_reprojects)
        rows.append(
            {
                "record_id": record_id,
                "matched_items": matched,
                "false_positive_items": false_positive,
                "missing_gold_items": missing,
                "complete_workflow": complete,
            }
        )

    tier_precision = {
        tier: {
            "correct": tier_correct[tier],
            "predicted": tier_predicted[tier],
            "precision": tier_correct[tier] / tier_predicted[tier] if tier_predicted[tier] else None,
        }
        for tier in ("E0", "E1", "E2", "E3")
    }
    overall_precision = overall_correct / overall_predicted if overall_predicted else None
    complete_rate = complete_records / len(extractions) if extractions else 0.0
    hard_gate_checks = {
        "E0": tier_precision["E0"]["precision"] is not None and tier_precision["E0"]["precision"] >= V2_1_THRESHOLDS["E0"],
        "E2": tier_precision["E2"]["precision"] is not None and tier_precision["E2"]["precision"] >= V2_1_THRESHOLDS["E2"],
        "E3": tier_precision["E3"]["precision"] is not None and tier_precision["E3"]["precision"] >= V2_1_THRESHOLDS["E3"],
        "overall": overall_precision is not None and overall_precision >= V2_1_THRESHOLDS["overall"],
        "test_source_false_positives": test_false_positives == 0,
        "constructor_false_positives": constructor_false_positives == 0,
        "complete_rate": complete_rate >= V2_1_THRESHOLDS["complete_rate"],
    }
    summary = {
        "schema_version": "qgis_source_grounded_v2_1_gate_summary_v1",
        "reviewed_records": len(extractions),
        "tier_precision": tier_precision,
        "overall_item_correct": overall_correct,
        "overall_item_predicted": overall_predicted,
        "overall_item_precision": overall_precision,
        "complete_records": complete_records,
        "complete_rate": complete_rate,
        "test_source_false_positives": test_false_positives,
        "constructor_false_positives": constructor_false_positives,
        "hard_gate_checks": hard_gate_checks,
        "hard_gate_passed": all(hard_gate_checks.values()),
        "v2_2_admission": "ready" if all(hard_gate_checks.values()) else "blocked",
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }
    return summary, rows
```

- [ ] **Step 4: Integrate v2 gate output into regression-mode CLI**

When `args.extractor_profile == "v2"` and regression mode is active:

```python
gate_summary, gate_rows = evaluate_v2_1_gate(extractions, adjudications)
_write_jsonl(output_dir / "v2_1_gate_results.jsonl", gate_rows)
_write_json(output_dir / "v2_1_gate_summary.json", gate_summary)
summary["v2_1_gate"] = gate_summary
```

When the CLI builds `extractor_code` for a v2 regression run, add:

```python
extractor_code["gate_module_sha256"] = _sha256(
    SRC / "gis_recommend" / "data" / "qgis_source_grounded_gate.py"
)
```

The CLI still returns 0 when extraction and evaluation complete, even when the gate is blocked, because blocked runs are valid diagnostic artifacts. Progression is controlled by `v2_2_admission`, not process exit status.

- [ ] **Step 5: Run gate and CLI tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_gate tests.test_qgis_source_grounded_cli -v
```

Expected: all tests pass; synthetic failing metrics produce `v2_2_admission=blocked` without granting training/taxonomy admission.

- [ ] **Step 6: Commit the precision gate evaluator**

```powershell
git add src/gis_recommend/data/qgis_source_grounded_gate.py tests/test_qgis_source_grounded_gate.py scripts/run_qgis_source_grounded_extractor.py tests/test_qgis_source_grounded_cli.py
git commit -m "Turn the locked review into an executable extractor precision gate" -m "The 35 adjudications now define deterministic operator and custom-component multisets, tier precision, false-positive counters and completeness admission." -m "Constraint: a blocked gate must still produce inspectable artifacts" -m "Rejected: Reusing v1 recall-only regression metrics | they cannot measure E3 or constructor precision" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: multiset matching, hard thresholds and CLI gate artifacts"
```

### Task 9: Run Full Verification And The Locked 35-Record Server Gate

**Files:**
- Create after successful run: `docs/reports/qgis_pilot/phase5_source_grounded_extractor_v2/v2_1_locked_35_regression/run_001/`
- Modify after successful run: `task_plan.md`
- Modify after successful run: `progress.md`
- Modify after successful run: `docs/PROJECT_CONTEXT.md`
- Modify after successful run: `docs/PROJECT_CONTEXT.zh-CN.md`

- [ ] **Step 1: Run focused local tests**

Run:

```powershell
python -m unittest tests.test_qgis_source_grounded_v1_compat tests.test_qgis_source_quality tests.test_qgis_source_grounded_extractor tests.test_qgis_source_grounded_semantic_compiler tests.test_qgis_source_grounded_v2 tests.test_qgis_source_grounded_gate tests.test_qgis_source_grounded_cli -v
```

Expected: all focused tests pass.

- [ ] **Step 2: Run stable-94 QGIS compatibility tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_qgis*.py"
```

Expected: all stable-94 QGIS tests pass. Record the exact count in the progress documents.

- [ ] **Step 3: Compile the changed Python files**

Run:

```powershell
python -m py_compile src/gis_recommend/data/qgis_source_quality.py src/gis_recommend/data/qgis_source_grounded_v2.py src/gis_recommend/data/qgis_source_grounded_gate.py scripts/run_qgis_source_grounded_extractor.py
```

Expected: exit code 0 and no output.

- [ ] **Step 4: Verify v1 remains the default from CLI help**

Run:

```powershell
python scripts/run_qgis_source_grounded_extractor.py --help
```

Expected: `--extractor-profile {v1,v2}` is present and help text states v1 is the default.

- [ ] **Step 5: Sync only the reviewed code and locked adjudication artifact to `/home/qy/system_redesign`**

Do not write to or delete from `/home/yll`. Verify server Git status before copying and do not overwrite unrelated server changes.

- [ ] **Step 6: Run locked 35 regression on the server in a new directory**

Run from `/home/qy/system_redesign`:

```bash
python scripts/run_qgis_source_grounded_extractor.py \
  --selection-jsonl outputs_v2/qgis_pilot/pilot_v1/phase3_signature_transfer_evaluation_50_v2/diagnostic_selection.jsonl \
  --review-csv outputs_v2/qgis_pilot/pilot_v1/phase3_signature_transfer_evaluation_50_v2/diagnostic_review.csv \
  --adjudications docs/reports/qgis_pilot/phase4_source_grounded_extractor_v1/holdout_35_adjudication_v1/human_adjudications.jsonl \
  --catalog outputs_v2/qgis_pilot/pilot_v1/phase4_source_grounded_extractor_v1/input_mirror/QGIS_Input.csv \
  --allowed-read-root /home/yll \
  --allowed-read-root /home/qy/system_redesign \
  --allowed-output-root /home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase5_source_grounded_extractor_v2 \
  --review-order-start 16 \
  --review-order-end 50 \
  --extractor-profile v2 \
  --regression-mode \
  --output-dir outputs_v2/qgis_pilot/pilot_v1/phase5_source_grounded_extractor_v2/v2_1_locked_35_regression/run_001
```

Expected:

- `records_extracted=35`
- `labels_read=true`
- `training_rows_emitted=0`
- `taxonomy_admission=not_granted`
- `training_admission=not_granted`
- `v2_1_gate_summary.json` exists
- all seven hard-gate checks are true before v2.2 work begins

- [ ] **Step 7: If any hard gate fails, stop v2.2 and create a rule-level failure report**

Write the failing records, evidence IDs, source/class decisions and false-positive/missing-gold items to the run report. Add or refine reusable structural tests before changing rules. Do not add record-ID-specific conditions.

- [ ] **Step 8: If all hard gates pass, copy the immutable run artifacts to the local report tree and verify hashes**

Local destination:

```text
docs/reports/qgis_pilot/phase5_source_grounded_extractor_v2/v2_1_locked_35_regression/run_001/
```

Verify every file listed in `hash_ledger.json` after transfer. Do not modify the copied artifacts after hash verification.

- [ ] **Step 9: Update durable project memory with measured results**

Record:

- exact test counts
- locked E0/E1/E2/E3 and overall precision
- test-source and constructor false-positive counts
- completeness rate
- `hard_gate_passed` and `v2_2_admission`
- changed files and commit hashes
- whether v2.2 is allowed to start

- [ ] **Step 10: Commit verified implementation and reports**

```powershell
git add src/gis_recommend/data/qgis_source_quality.py src/gis_recommend/data/qgis_source_grounded_v2.py src/gis_recommend/data/qgis_source_grounded_gate.py scripts/run_qgis_source_grounded_extractor.py tests/test_qgis_source_grounded_v1_compat.py tests/test_qgis_source_quality.py tests/test_qgis_source_grounded_v2.py tests/test_qgis_source_grounded_gate.py tests/test_qgis_source_grounded_cli.py docs/reports/qgis_pilot/phase5_source_grounded_extractor_v2/v2_1_locked_35_regression/run_001 task_plan.md progress.md docs/PROJECT_CONTEXT.md docs/PROJECT_CONTEXT.zh-CN.md
git commit -m "Decide extractor completeness work with measured precision evidence" -m "Extractor v2.1 has been verified against the locked 35-record review and records an explicit admission decision for v2.2." -m "Constraint: training and taxonomy admission remain not granted" -m "Confidence: high" -m "Scope-risk: moderate" -m "Directive: Begin v2.2 only when every v2.1 hard gate is true" -m "Tested: focused suites, stable-94 QGIS suite, py_compile and locked server regression"
```

## Completion Criteria

The implementation phase is complete only when all of the following are true:

- v1 default and explicit-v1 outputs are semantically identical.
- Source and class decisions are present for every v2 record.
- Rejected sources emit zero operator/custom items.
- Constructor and configuration evidence is audit-only.
- Reviewed identity gaps resolve exactly or abstain when the catalog is ambiguous/missing.
- Legacy Eliminate emits one bounded identity and suppresses its internal intersection/union substeps.
- Duplicate groups retain every evidence ID and never collapse distinct outputs.
- All focused and stable-94 QGIS tests pass.
- The locked 35 run produces a complete hash ledger and explicit hard-gate decision.
- No taxonomy/training admission is granted and no training rows are emitted.
- v2.2 remains blocked unless every v2.1 hard gate passes.
