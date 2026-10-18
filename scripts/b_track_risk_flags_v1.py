#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Risk-flag analyzer V1 (calibrated 2026-10-18, owner-approved P0).

Frozen definitions (see B_TRACK_RISK_FLAG_SPEC_V1.md):

  ui_control      interactive Earth Engine UI widgets (Button/Select/Slider/
                  Checkbox/Textbox/Panel/Map/SplitPanel) or Map.onClick.
  ui_chart        ui.Chart.* calls (chart output, not analysis logic).
  ui_display      ui.Label / ui.Thumbnail (display-only).
  map_display     Map.addLayer / Map.setCenter / Map.centerObject /
                  Map.setOptions / Map.add / Map.layers (display scaffolding).
  duplicate_block any contiguous triple of substantive normalized lines that
                  occurs >= 2 times.
  duplicate_line  any substantive normalized line occurring >= 3 times.
  nonliteral_asset_arg  ee.ImageCollection|ee.Image|ee.FeatureCollection first
                  argument is a bare identifier or a string concatenation
                  (provenance is not visible at the call site).  NOTE: this is
                  a review prompt, not proof of an indirect asset.
  numeric/array first arguments are NOT flagged.

Substantive line = comment-stripped, whitespace-stripped, trailing-semicolon
stripped, length >= 15, and not only brackets/punctuation.

Read-only; importable.  CLI:
  python scripts/b_track_risk_flags_v1.py --script <path> [--script ...]
  python scripts/b_track_risk_flags_v1.py --json <path>
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

RULES_VERSION = "V1_calibrated_20261018"
CALL_RE = re.compile(r"\bee\.(ImageCollection|Image|FeatureCollection)\s*\(")
BARE_ID_RE = re.compile(r"^[A-Za-z_$][\w$]*$")
NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
PUNCT_ONLY = re.compile(r"^[(){}\[\];,.:+\-*/%&|^!<>=?~`'\"\\s]*$")
UI_CONTROL_RE = re.compile(r"\bui\.(Button|Select|Slider|Checkbox|Textbox|Panel|Map|SplitPanel)\b")
UI_CHART_RE = re.compile(r"\bui\.Chart\.")
UI_DISPLAY_RE = re.compile(r"\bui\.(Label|Thumbnail)\b")
MAP_DISPLAY_RE = re.compile(r"\bMap\.(addLayer|setCenter|centerObject|setOptions|add|layers)\b")
MAP_INTERACTIVE_RE = re.compile(r"\bMap\.onClick\b")
STR_LITERAL_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")


def _first_arg(src, open_idx):
    """Return (raw_first_arg, end_idx) for the '(' at open_idx."""
    depth = 0
    i = open_idx
    start = open_idx + 1
    while i < len(src):
        ch = src[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return src[start:i], i
        elif ch == "," and depth == 1:
            return src[start:i], i
        i += 1
    return src[start:], len(src)


def normalize_line(line):
    # strip line comment (documented limitation: a // inside a string is also
    # stripped; scripts rarely contain such strings and both versions of the
    # rule share this behavior)
    line = line.split("//", 1)[0]
    line = re.sub(r"\s+", "", line)
    line = line.rstrip(";")
    return line


def duplicate_stats(src):
    lines = [normalize_line(l) for l in src.splitlines()]
    subs = [l for l in lines if len(l) >= 15 and not PUNCT_ONLY.match(l)]
    line_counts = Counter(subs)
    dup_line_max = max(line_counts.values()) if line_counts else 0
    triple = Counter(tuple(subs[i:i + 3]) for i in range(len(subs) - 2))
    triple_max = max(triple.values()) if triple else 0
    return {
        "substantive_lines": len(subs),
        "dup_line_max": dup_line_max,
        "dup_triple_max": triple_max,
        "duplicate_line": dup_line_max >= 3,
        "duplicate_block": triple_max >= 2,
    }


def asset_args(src):
    literal, bare, concat, other = [], [], [], []
    for m in CALL_RE.finditer(src):
        open_idx = m.end() - 1
        arg, _ = _first_arg(src, open_idx)
        a = arg.strip()
        if not a:
            continue
        if a[0] in "'\"":
            # string literal or concatenation
            if "+" in a:
                concat.append(a[:160])
                for mm in STR_LITERAL_RE.finditer(a):
                    lit = mm.group(1) if mm.group(1) is not None else mm.group(2)
                    if lit:
                        literal.append(lit)
            else:
                mm = STR_LITERAL_RE.match(a)
                if mm:
                    lit = mm.group(1) if mm.group(1) is not None else mm.group(2)
                    if lit:
                        literal.append(lit)
        elif NUM_RE.match(a):
            continue
        elif a.startswith("["):
            continue
        elif BARE_ID_RE.match(a):
            bare.append(a)
        else:
            other.append(a[:160])
    return {
        "literal_assets": sorted(set(literal)),
        "bare_identifier_args": sorted(set(bare)),
        "concat_args": concat,
        "other_nonliteral_args": other,
        "nonliteral_asset_arg": bool(bare or concat),
    }


def analyze_source(src):
    ui_control = len(UI_CONTROL_RE.findall(src))
    ui_chart = len(UI_CHART_RE.findall(src))
    ui_display = len(UI_DISPLAY_RE.findall(src))
    map_display = len(MAP_DISPLAY_RE.findall(src))
    map_interactive = len(MAP_INTERACTIVE_RE.findall(src))
    dup = duplicate_stats(src)
    assets = asset_args(src)
    flags = []
    if ui_control or map_interactive:
        flags.append("ui_interactive")
    if ui_chart:
        flags.append("ui_chart")
    if ui_display:
        flags.append("ui_display")
    if map_display:
        flags.append("map_display")
    if dup["duplicate_block"]:
        flags.append("duplicate_block")
    if dup["duplicate_line"]:
        flags.append("duplicate_line")
    if assets["nonliteral_asset_arg"]:
        flags.append("nonliteral_asset_arg")
    if assets["literal_assets"]:
        flags.append("literal_asset")
    dup_level = max(dup["dup_line_max"] if dup["duplicate_line"] else 0,
                    dup["dup_triple_max"] if dup["duplicate_block"] else 0)
    dup["dup_severity"] = ("none" if dup_level == 0 else
                           "high" if dup_level >= 10 else
                           "low" if dup_level <= 4 else "medium")
    assets["nonliteral_count"] = len(assets["bare_identifier_args"]) + len(assets["concat_args"])
    assets["nonliteral_severity"] = ("none" if assets["nonliteral_count"] == 0 else
                                     "high" if assets["nonliteral_count"] >= 5 else
                                     "low" if assets["nonliteral_count"] == 1 else "medium")
    return {
        "rules_version": RULES_VERSION,
        "ui_control_calls": ui_control,
        "ui_chart_calls": ui_chart,
        "ui_display_calls": ui_display,
        "map_display_calls": map_display,
        "map_interactive_calls": map_interactive,
        **dup,
        **assets,
        "flags": flags,
    }


def analyze_file(path):
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    out = analyze_source(src)
    out["path"] = str(path)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", action="append", default=[])
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    if args.json:
        data = json.loads(Path(args.json).read_text(encoding="utf-8"))
        cases = data["cases"]
        ok = 0
        for c in cases:
            got = analyze_source(c["source"])
            got_flags = set(got["flags"])
            exp = set(c["expected_flags"])
            pass_ = got_flags == exp
            ok += pass_
            print(("PASS" if pass_ else "FAIL"), c["id"],
                  "expected", sorted(exp), "got", sorted(got_flags))
            if not pass_:
                for k in ("bare_identifier_args", "concat_args", "dup_line_max",
                          "dup_triple_max", "ui_control_calls", "map_display_calls"):
                    print("   ", k, got[k])
        print(f"{ok}/{len(cases)} passed")
    for p in args.script:
        print(json.dumps(analyze_file(p), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
