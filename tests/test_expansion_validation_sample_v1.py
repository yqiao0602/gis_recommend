# -*- coding: utf-8 -*-
"""Unit tests for the frozen expansion sampling design (WP-B v1).

Synthetic fixtures only; no corpus sampling executed.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from build_expansion_validation_sample_v1 import (  # noqa: E402
    MIN_CONTROL,
    MIN_PER_DIFFICULTY_LAYER,
    MIN_RANDOM,
    PILOT_EXCLUSIONS,
    FROZEN_SEED,
    algorithm_r_reservoir,
    detect_l1,
    detect_l2,
    detect_l3,
    detect_l4,
    detect_l5,
    sample,
)
from run_wp_a_detector_backtest_v1 import analyze_script  # noqa: E402


# ---------------- frozen constants ----------------

def test_frozen_constants():
    assert FROZEN_SEED == 20261009
    assert MIN_PER_DIFFICULTY_LAYER == 5
    assert MIN_CONTROL == 10
    assert MIN_RANDOM == 10
    assert PILOT_EXCLUSIONS == {
        "script_36595", "script_275285", "script_93009",
        "script_302840", "script_405410", "script_269131"}


# ---------------- layer detectors on synthetic sources ----------------

def test_l1_external_dependency_hit():
    a = {"declared": {}, "uses": [{"name": "AOI", "pos": (5, 0)}],
         "calls": [], "comment_text": "", "parse_comments": []}
    assert detect_l1(a) == ["AOI"]


def test_l2_ignores_visualization_params():
    src = "var pi_all = a.add(b);\nvar myVis = {min: 0};\nvar z = c.add(d);"
    out = detect_l2(analyze_script(src))
    assert "pi_all" in out
    assert not any("vis" in v.lower() for v in out)


def test_l3_role_coexistence_hit():
    src = "var v = a.add(b);\nMap.addLayer(v, {}, 'm');\nvar w = v.multiply(2);"
    assert detect_l3(analyze_script(src)) == ["v"]


def test_l4_repeated_block_detection():
    block = ("var rf = ee.Classifier.smileRandomForest({numberOfTrees: 100});\n"
             "var trained = rf.train(ftTrain, 'coi', bands);\n"
             "var pred = trained.classify(image.select(bands));\n")
    src = block * 3 + "var x1 = a.add(1);\n" * 4
    hits = detect_l4(src)
    assert hits, "repeated 3x block must be detected"
    assert hits[0]["occurrences"] >= 3


def test_l4_no_false_positive_on_unique_blocks():
    src = ("var a = ee.Image(1).add(2);\n"
           "var b = ee.Image(2).subtract(3);\n"
           "var c = ee.Image(3).multiply(4);")
    assert detect_l4(src) == []


def test_l5_multi_definition_detection():
    src = ("var formula = a.add(1);\n"
           "var pi = a.multiply(2);\n"
           "var other = a.add(3);\n"
           "var pi = a.multiply(4);")
    hits = detect_l5(src)
    names = {h["variable"] for h in hits}
    assert "pi" in names
    entry = [h for h in hits if h["variable"] == "pi"][0]
    assert len(entry["definition_lines"]) == 2


# ---------------- Algorithm-R reservoir determinism ----------------

def test_reservoir_deterministic_and_covers_stream():
    stream = [f"s{i:03d}" for i in range(100)]
    r1 = algorithm_r_reservoir(stream, 10, __import__("random").Random(20261009))
    r2 = algorithm_r_reservoir(stream, 10, __import__("random").Random(20261009))
    assert r1 == r2
    assert len(r1) == 10
    assert all(s in stream for s in r1)


# ---------------- sampling driver on synthetic manifest ----------------

def _make_split(tmp, n=60):
    root = os.path.join(tmp, "scripts")
    os.makedirs(root, exist_ok=True)
    entries = []
    block = ("var rf = ee.Classifier.smileRandomForest({numberOfTrees: 100});\n"
             "var trained = rf.train(ft, 'c', b);\n"
             "var pred = trained.classify(img.select(b));\n")
    for i in range(n):
        sid = f"script_{i:06d}"
        if i % 6 == 0:
            body = "var out = AOI.clip(1);\nvar w = out.multiply(2);\nMap.addLayer(w, {}, 'x');"
        elif i % 6 == 1:
            body = "var dead = a.add(b);\nvar z = c.add(d);"
        elif i % 6 == 2:
            body = ("var v = a.add(b);\nMap.addLayer(v, {}, 'm');\nvar w = v.multiply(2);")
        elif i % 6 == 3:
            body = block * 3 + "var tail = q.add(1);"
        elif i % 6 == 4:
            body = "var f1 = a.add(1);\nvar f2 = b.add(2);\nvar f1 = a.multiply(3);"
        else:
            # clean control: every declared variable consumed downstream,
            # no dead code, no repeats, no multi-formula, no externals
            body = ("var base = ee.Image(1);\n"
                    "var only = base.add(2);\n"
                    "var fin = only.multiply(3);\n"
                    "var fin2 = fin.subtract(1);\n"
                    "Map.addLayer(fin2, {}, 'done');")
        p = os.path.join(root, f"{sid}.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        entries.append({"script": sid, "path": os.path.relpath(p, tmp).replace("\\", "/")})
    # add pilot scripts (must be excluded)
    for pid in sorted(PILOT_EXCLUSIONS):
        entries.append({"script": pid, "path": "nonexistent/" + pid + ".txt"})
    return entries


def test_sample_excludes_pilots_and_is_deterministic():
    with tempfile.TemporaryDirectory() as tmp:
        entries = _make_split(tmp)
        split_path = os.path.join(tmp, "split.json")
        with open(split_path, "w", encoding="utf-8") as f:
            json.dump(entries, f)

        # manifest paths are repo-relative; run from repo root but with the
        # manifest in tmp — simulate by chdir to tmp and using absolute paths
        # inside the manifest instead (absolute paths are used as-is).
        abs_entries = [
            {**e, "path": os.path.join(tmp, e["path"]).replace("\\", "/")}
            for e in entries]
        with open(split_path, "w", encoding="utf-8") as f:
            json.dump(abs_entries, f)

        r1 = sample(split_path)
        r2 = sample(split_path)

        assert r1 == r2, "sampling must be deterministic"
        all_selected = {s for ids in r1["selected"].values() for s in ids}
        assert not (all_selected & PILOT_EXCLUSIONS), "pilots must be excluded"
        assert len(r1["selected"]["R_random_independent"]) == MIN_RANDOM
        assert len(r1["selected"]["C_control"]) >= 1
        assert r1["deduplicated_script_total"] == len(all_selected)


def test_sample_records_split_sha():
    with tempfile.TemporaryDirectory() as tmp:
        entries = _make_split(tmp, n=12)
        split_path = os.path.join(tmp, "split.json")
        abs_entries = [
            {**e, "path": os.path.join(tmp, e["path"]).replace("\\", "/")}
            for e in entries]
        with open(split_path, "w", encoding="utf-8") as f:
            json.dump(abs_entries, f)
        r = sample(split_path)
        assert r["train_split"]["sha256"]
        assert r["train_split"]["path"].endswith("split.json")
