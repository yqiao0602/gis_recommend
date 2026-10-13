# -*- coding: utf-8 -*-
"""Unit tests for WP-A detectors (A1-A4), synthetic fixtures only.

Run: python -m pytest tests/test_wp_a_detector_backtest_v1.py -q
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from run_wp_a_detector_backtest_v1 import (  # noqa: E402
    analyze_script,
    detect_a1,
    detect_a1_self_references,
    detect_a2,
    detect_a3,
    detect_a4,
)


def _analyzed(src):
    return analyze_script(src)


# ---------------- A1: candidate-only rule (owner revision 1) ----------------

def test_a1_undeclared_is_candidate_not_external():
    a = _analyzed("var x = AOI.clip(aoi);")
    cands = {c["variable"]: c for c in detect_a1(a)}
    # AOI undeclared -> candidate pending human; never auto external_prebinding
    assert "AOI" in cands
    assert cands["AOI"]["classification"] == "candidate_pending_human"
    assert cands["AOI"]["definition_location"] == "unavailable_in_source"


def test_a1_declared_variable_no_false_positive():
    a = _analyzed("var aoi = ee.Geometry.Polygon([1]);var x = aoi.clip(1);")
    names = {c["variable"] for c in detect_a1(a)}
    assert "aoi" not in names
    assert "x" not in names


def test_a1_self_reference_in_initializing_assignment():
    a = _analyzed("soil = soil.select('b0');\nvar y = soil.add(1);")
    extra = detect_a1_self_references(a, detect_a1(a))
    names = {c["variable"] for c in extra}
    assert "soil" in names
    entry = [c for c in extra if c["variable"] == "soil"][0]
    assert "self_reference_in_initializing_assignment" in entry["evidence"]


def test_a1_assignment_lhs_is_not_a_use():
    a = _analyzed("table = ee.FeatureCollection('x');")
    cands = [c for c in detect_a1(a) if c["variable"] == "table"]
    # LHS assignment target alone is not an undeclared use
    assert cands == []


# ---------------- A2: AST-based use counting ----------------

def test_a2_zero_uses_is_unconsumed():
    src = ("var q = ee.Image(1);\n"
           "var r = q.add(1);\n"
           "var pi_all = q.multiply(r);\n"
           "var out = q.add(r);\n"
           "var z = out.add(1);")
    a = _analyzed(src)
    rows = {r["variable"]: r for r in detect_a2(a)}
    assert rows["pi_all"]["status"] == "unconsumed"
    assert rows["pi_all"]["post_definition_uses"] == 0
    assert rows["out"]["status"] == "analysis_chain"


def test_a2_use_via_function_argument_counts():
    a = _analyzed("var fs = a.add(b);\nMap.addLayer(fs, {}, 't');")
    rows = {r["variable"]: r for r in detect_a2(a)}
    # Map.addLayer is presentation -> presentation_only
    assert rows["fs"]["status"] == "presentation_only"
    assert rows["fs"]["post_definition_uses"] == 1


def test_a2_text_mention_is_not_a_use():
    a = _analyzed("var pi = a.add(b);\n// pi is unused here\nvar z = q.add(r);")
    rows = {r["variable"]: r for r in detect_a2(a)}
    assert rows["pi"]["post_definition_uses"] == 0


def test_a2_member_access_counts_as_use():
    a = _analyzed("var t = a.add(b);\nvar u = t.foo(1);")
    rows = {r["variable"]: r for r in detect_a2(a)}
    assert rows["t"]["post_definition_uses"] == 1


# ---------------- A3: unknown API never defaults to analysis ----------------

def test_a3_unknown_api_goes_to_review_queue():
    a = _analyzed("weirdLib.doThing(x);")
    res = detect_a3(a["calls"])
    assert res["class_counts"].get("analysis", 0) == 0
    assert len(res["unknown_review_queue"]) == 1
    assert res["unknown_review_queue"][0]["path"] == "weirdLib.doThing"


def test_a3_preregistered_table():
    a = _analyzed(
        "var x = ee.Image(1);\n"
        "Map.addLayer(x, {}, 'm');\n"
        "Export.image.toDrive({image: x});\n"
        "var y = x.multiply(2);"
    )
    res = detect_a3(a["calls"])
    assert res["class_counts"]["presentation"] == 1
    assert res["class_counts"]["export"] == 1
    # ee.Image(1) constructor + x.multiply(2)
    assert res["class_counts"]["analysis"] == 2


def test_a3_roles_coexist():
    a = _analyzed(
        "var v = a.add(b);\n"
        "Map.addLayer(v, {}, 'm');\n"
        "var w = v.multiply(2);"
    )
    res = detect_a3(a["calls"])
    # v is consumed by both a presentation call and an analysis call
    rows = {r["variable"]: r for r in detect_a2(a)}
    assert rows["v"]["consuming_call_classes"] == ["analysis", "presentation"]
    assert rows["v"]["status"] == "analysis_chain"


# ---------------- A4: dedup keeps original evidence ----------------

def test_a4_logical_dedup_preserves_via_conflict():
    edges = [
        {"from": "dem", "to": "count_Dem", "via": "multiply 47.9", "use_line": 179},
        {"from": "dem", "to": "count_Dem", "via": "also source of count chain",
         "use_line": 179},
        {"from": "pop", "to": "count_pop", "via": "multiply 0.75", "use_line": 187},
    ]
    deduped, dups_logical, dups_strict = detect_a4(edges)
    assert (len(deduped), dups_logical, dups_strict) == (2, 1, 0)
    rec = [r for r in deduped if r["from"] == "dem"][0]
    assert rec["via_conflict"] is True
    assert "also source of count chain" in rec["via_all"]  # not silently dropped
    assert len(rec["merged_originals"]) == 1


def test_a4_no_dedup_when_operation_differs():
    edges = [
        {"from": "a", "to": "b", "via": "add", "use_line": 10},
        {"from": "a", "to": "c", "via": "add", "use_line": 10},
        {"from": "a", "to": "b", "via": "multiply", "use_line": 12},
    ]
    deduped, dups_logical, _ = detect_a4(edges)
    assert (len(deduped), dups_logical) == (3, 0)


# ---------------- a3-fix-round v1.1 regression tests ----------------

def test_v1_1_nested_call_chain_resolved():
    src = ("var d = ee.Image(1);\n"
           "var m = d.filter(f).mean();")
    a = analyze_script(src)
    classes = [c["classification"] for c in a["calls"]]
    assert "unknown" not in classes, classes
    assert classes.count("analysis") == 3  # ee.Image, .filter, .mean


def test_v1_1_reduceRegion_nested_not_unknown():
    src = ("var ic = ee.Image(1);\n"
           "var s = ic.select('b1').reduceRegion({reducer: r});")
    a = analyze_script(src)
    classes = [c["classification"] for c in a["calls"]]
    assert "unknown" not in classes, classes


def test_v1_1_console_log_and_ui_map_presentation():
    a = analyze_script("console.log(x);\nvar m = ui.Map();")
    by_path = {c["path"]: c["classification"] for c in a["calls"]}
    assert by_path["console.log"] == "presentation"
    assert by_path["ui.Map"] == "presentation"


def test_v1_1_map_setoptions_layers_presentation():
    a = analyze_script("Map.setOptions('satellite');\nMap.layers().reset([l]);")
    classes = [c["classification"] for c in a["calls"]]
    assert "presentation" in classes
    # no call regresses to unknown
    assert "unknown" not in [c for c in classes], classes


def test_v1_1_candidate_root_classified_by_method():
    # ext is an A1 candidate (undeclared); known data methods -> analysis,
    # unknown methods stay unknown (no forced classification). Nested-chain
    # nodes keep path=None (strict dotted_path unchanged) but classify via
    # the root+method fallback.
    src = "var a = ext.filter(f).select('b');\nvar b = ext.weirdUnknownMethod();"
    a = analyze_script(src)
    calls = a["calls"]
    by_path = {c["path"]: c["classification"] for c in calls if c["path"]}
    nested = [c["classification"] for c in calls if c["path"] is None]
    assert by_path["ext.filter"] == "analysis"
    assert by_path["ext.weirdUnknownMethod"] == "unknown"
    assert nested == ["analysis"]  # nested .select classified via fallback


def test_v1_1_visualize_method_presentation():
    src = "var d = ee.Image(1);\nvar v = d.select('b').visualize({});"
    a = analyze_script(src)
    classes = [c["classification"] for c in a["calls"]]
    assert "presentation" in classes
