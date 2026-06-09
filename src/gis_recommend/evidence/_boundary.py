# -*- coding: utf-8 -*-
"""Snapshot/report boundary constants.

Static import verification registry.
Defines which modules may import which other modules.
Report-only metadata; importing this module must not gate runtime execution.
"""

__all__ = [
    "FORBIDDEN_IMPORT_GRAPH",
    "FORBIDDEN_METHOD_GRAPH",
    "SNAPSHOT_RUNTIME_ACCESS",
    "EDGE_GRAPH",
    "SUPPORTED_FORMAT_VERSIONS",
    "ONLY_ALLOWED_RUNTIME_GATES",
    "FORBIDDEN_AS_GATE",
    "verify_import_boundary",
]

__allowed_imports__ = ["sys", "typing"]
__forbidden_imports__ = []
__layer__ = "snapshot_report"

# ---------------------------------------------------------------------------
# Format version gate — the ONE allowed semantic gate (purely structural)
# ---------------------------------------------------------------------------

SUPPORTED_FORMAT_VERSIONS: set[str] = {
    "gis_recommend.checkpoint.v1",
    "gis_recommend.checkpoint.v5",
}

# ---------------------------------------------------------------------------
# Forbidden import adjacency list (MVCS §B)
# ---------------------------------------------------------------------------

FORBIDDEN_IMPORT_GRAPH: dict[str, list[str]] = {
    "training":    ["evidence"],
    "inference":   ["evidence"],
    "models":      ["evidence"],
    "pipelines":   ["evidence"],
    "evidence":    [],
}

# ---------------------------------------------------------------------------
# Forbidden method access adjacency list (MVCS §B)
# ---------------------------------------------------------------------------

FORBIDDEN_METHOD_GRAPH: dict[tuple[str, str], list[str]] = {
    ("training", "evidence"): [
        "classify_checkpoint_validity",
        "reconstruct_lineage",
        "recompute_metrics",
        "compare_metrics",
        "diff_dispatch",
        "generate_archaeology_report",
        "ValidityReport",
        "ComparisonReport",
        "LineageGraph",
        "RecomputeReport",
        "DispatchDiff",
        "ArchaeologyReport",
        "RecomputeContext",
    ],
}

# ---------------------------------------------------------------------------
# Snapshot field → runtime access (MVCS §B)
# ---------------------------------------------------------------------------

SNAPSHOT_RUNTIME_ACCESS: dict[str, str] = {
    "model_state_dict":             "ALLOWED:load_only",
    "task_classifier_state_dict":   "ALLOWED:load_only",
    "epoch":                        "ALLOWED:display_only",
    "model_config":                 "ALLOWED:display_only",
    "val_loss":                     "ALLOWED:display_only",
    "ar_token_acc":                 "ALLOWED:display_only",
    "ar_seq_em":                    "ALLOWED:display_only",
    "provenance":                   "FORBIDDEN:runtime_access",
    "metric_bundle":                "FORBIDDEN:runtime_access",
}

# ---------------------------------------------------------------------------
# Cross-layer edge graph (MVCS §B)
# ---------------------------------------------------------------------------

EDGE_GRAPH: dict[tuple[str, str], str] = {
    ("runtime",      "runtime"):      "ALLOWED",
    ("runtime",      "snapshot"):     "ONE_WAY:torch_save",
    ("runtime",      "interpretive"): "ALLOWED:no_dependency",
    ("snapshot",     "runtime"):      "RESTRICTED:model_state_dict_only",
    ("snapshot",     "snapshot"):     "FORBIDDEN",
    ("snapshot",     "interpretive"): "ALLOWED:read_only",
    ("interpretive", "runtime"):      "FORBIDDEN",
    ("interpretive", "snapshot"):     "FORBIDDEN",
    ("interpretive", "interpretive"): "ALLOWED:pure_composition",
}

# ---------------------------------------------------------------------------
# Gate whitelist (MVCS §C)
# ---------------------------------------------------------------------------

ONLY_ALLOWED_RUNTIME_GATES: list[dict] = [
    {
        "gate_id": 1,
        "name": "format_version_check",
        "trigger": "torch.load",
        "check": "checkpoint.provenance.format_version IN SUPPORTED_FORMATS",
        "failure": "raise StructuralIncompatibilityError",
        "scope": "structural_only",
    },
    {
        "gate_id": 2,
        "name": "model_state_dict_shape_check",
        "trigger": "after gate_1 passes",
        "check": "keys_match AND all_shapes_match",
        "failure": "raise StructuralIncompatibilityError",
        "scope": "structural_only",
    },
]

FORBIDDEN_AS_GATE: list[dict] = [
    {"field": "provenance.run_id",                     "reason": "semantic identity"},
    {"field": "provenance.parent_run_id",              "reason": "lineage is informational"},
    {"field": "provenance.code_identity.*",            "reason": "code version is informational"},
    {"field": "provenance.config_snapshot.*",          "reason": "config is informational"},
    {"field": "provenance.dataset_identity.*",         "reason": "dataset identity is informational"},
    {"field": "provenance.framework_identity.*",       "reason": "framework is informational"},
    {"field": "metric_bundle.selector_policy",         "reason": "selector is historical record"},
    {"field": "metric_bundle.decode_policy",           "reason": "decode policy is metric context"},
    {"field": "metric_bundle.metrics[*].value",        "reason": "metric values are archival"},
    {"field": "val_loss",                              "reason": "metric is informational"},
    {"field": "ar_token_acc",                          "reason": "metric is informational"},
    {"field": "ar_seq_em",                             "reason": "metric is informational"},
    {"field": "epoch",                                 "reason": "epoch is informational"},
]

# ---------------------------------------------------------------------------
# Boundary verification (stub — no logic)
# ---------------------------------------------------------------------------

def verify_import_boundary(caller_module: str, target_module: str) -> None:
    """Report-only compatibility hook; never blocks imports or execution."""
    return None
