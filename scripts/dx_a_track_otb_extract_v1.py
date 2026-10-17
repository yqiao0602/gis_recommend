#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A-track P0 OTB evidence extraction (DX_EXPERIMENT_DESIGN_RULING_OWNER_V1.md:
A1 evidence base = OTB 115 cards, official-source driven).

Parses the pinned upstream OTB 8.1.2 application sources
(_external_evidence/otb_upstream_v1, tag 8.1.2, commit b3eb5603...) and emits a
structured evidence layer: per-application description, parameters (key, human
name, OTB type, io class, required, default, description, choices) and outputs.

This is EVIDENCE, not the profile patch: the v0_5 builder consumes it separately
and marks anything not extractable as "当前证据无法确认" (never guessed).

Usage: python dx_a_track_otb_extract_v1.py [--app Aggregate,TrainImagesClassifier]
Output: dx50_full_v1/a_track_p0_v1/otb_evidence_812_v1.json (+ pilot preview to stdout)
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OTB = (REPO.parent / "_external_evidence/otb_upstream_v1")
APP_DIR = OTB / "Modules/Applications"
OUT = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
               "dx50_full_v1/a_track_p0_v1/otb_evidence_812_v1.json"))

PIN = {"tag": "8.1.2", "commit": "b3eb56034e371846c39ae249f837b6c14b3b5039",
       "mirror": "https://github.com/orfeotoolbox/OTB",
       "layout": "Modules/Applications/App<Name>/app/otb<Name>.cxx"}

INPUT_CLASSES = {
    "InputImage": "raster", "InputImageList": "raster",
    "ComplexInputImage": "raster_complex",
    "InputVectorData": "vector", "InputVectorDataList": "vector",
    "InputFilename": "file", "InputFilenameList": "file",
    "InputProcessXML": "file_xml",
}
OUTPUT_CLASSES = {
    "OutputImage": "raster", "ComplexOutputImage": "raster_complex",
    "OutputVectorData": "vector", "OutputFilename": "file",
    "OutputProcessXML": "file_xml",
}
LITERAL_TYPES = {"String", "Int", "Float", "Double", "Bool", "Radius", "RAM",
                 "ListView", "Choice", "Bands", "Field", "StringList"}

CALL_RE = re.compile(
    r"\b(AddParameter|AddChoice|SetParameterDescription|MandatoryOn|MandatoryOff|"
    r"SetParameterString|SetParameterStringList|SetDefaultParameterInt|"
    r"SetDefaultParameterFloat|SetDefaultParameterDouble|SetParameterInt|"
    r"SetParameterFloat|SetParameterDouble|SetName|SetDescription)\s*\(")
LITS_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def read_calls(text):
    """Yield (func, [arg-strings]) for every matched call, paren-matched with
    quote awareness; adjacent string literals in an arg are concatenated."""
    out = []
    for m in CALL_RE.finditer(text):
        i = m.end()  # at '('
        depth, j, in_str, esc = 1, i, False, False
        while j < len(text) and depth:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            j += 1
        body = text[i:j - 1]
        args, cur, k, in_str, esc, depth2 = [], [], 0, False, False, 0
        while k < len(body):
            c = body[k]
            if in_str:
                cur.append(c)
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
                cur.append(c)
            elif c in "(<":
                depth2 += 1
                cur.append(c)
            elif c in ")>":
                depth2 -= 1
                cur.append(c)
            elif c == "," and depth2 == 0:
                args.append("".join(cur))
                cur = []
            else:
                cur.append(c)
            k += 1
        if cur:
            args.append("".join(cur))
        parsed = []
        for a in args:
            lits = LITS_RE.findall(a)
            if lits:
                parsed.append("".join(lits))
            else:
                parsed.append(a.strip())
        out.append((m.group(1), parsed))
    return out


def unescape(s):
    return (s.replace('\\n', '\n').replace('\\t', ' ')
            .replace('\\"', '"').replace('\\\\', '\\'))


def classify(ptype):
    if ptype in INPUT_CLASSES:
        return "input", INPUT_CLASSES[ptype]
    if ptype in OUTPUT_CLASSES:
        return "output", OUTPUT_CLASSES[ptype]
    if ptype in LITERAL_TYPES:
        return "literal", "literal"
    if ptype == "Group":
        return "section", "section"
    return "unknown", "unknown"


def parse_app(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    calls = read_calls(text)
    app = {"otb_name": None, "description": None, "parameters": {},
           "order": [], "unknown_calls": 0}
    for fn, args in calls:
        try:
            if fn == "SetName" and app["otb_name"] is None:
                app["otb_name"] = args[0]
            elif fn == "SetDescription" and app["description"] is None:
                app["description"] = unescape(args[0])
            elif fn == "AddParameter" and len(args) >= 3:
                ptype = re.sub(r"^ParameterType_", "", str(args[0]))
                key, human = args[1], args[2]
                io, norm = classify(ptype)
                app["parameters"][key] = {
                    "key": key, "human_name": human, "otb_type": ptype,
                    "io_class": io, "normalized_type": norm,
                    "required": False, "default": None, "description": None,
                    "choices": {}}
                app["order"].append(key)
            elif fn == "AddChoice" and len(args) >= 2:
                key, label = args[0], args[1]
                parent = key.rsplit(".", 1)[0]
                if parent in app["parameters"]:
                    app["parameters"][parent]["choices"][key] = {
                        "label": label, "description": None}
            elif fn == "SetParameterDescription" and len(args) >= 2:
                key, desc = args[0], unescape(args[1])
                if key in app["parameters"]:
                    app["parameters"][key]["description"] = desc
                elif "." in key:
                    parent, leaf = key.rsplit(".", 1)
                    if parent in app["parameters"] and \
                            key in app["parameters"][parent]["choices"]:
                        app["parameters"][parent]["choices"][key][
                            "description"] = desc
            elif fn == "MandatoryOn" and args:
                if args[0] in app["parameters"]:
                    app["parameters"][args[0]]["required"] = True
            elif fn == "MandatoryOff" and args:
                if args[0] in app["parameters"]:
                    app["parameters"][args[0]]["required"] = False
            elif fn in ("SetParameterString", "SetParameterInt",
                        "SetParameterFloat", "SetParameterDouble",
                        "SetDefaultParameterInt", "SetDefaultParameterFloat",
                        "SetDefaultParameterDouble") and len(args) >= 2:
                if args[0] in app["parameters"]:
                    app["parameters"][args[0]]["default"] = args[1]
            elif fn == "SetParameterStringList" and len(args) >= 2:
                if args[0] in app["parameters"]:
                    app["parameters"][args[0]]["default"] = args[1:]
        except (IndexError, KeyError):
            app["unknown_calls"] += 1
    app["parameters"] = [app["parameters"][k] for k in app["order"]]
    del app["order"]
    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=None,
                    help="comma-separated SetName filter for a pilot run")
    args = ap.parse_args()

    files = sorted(p for p in APP_DIR.glob("App*/app/otb*.cxx")
                   if "/test/" not in str(p).replace("\\", "/").lower())
    apps, misses = {}, []
    for p in files:
        a = parse_app(p)
        if not a["otb_name"]:
            misses.append(str(p))
            continue
        rel = p.relative_to(OTB).as_posix()
        rec = {"otb_name": a["otb_name"], "description": a["description"],
               "source": {"path": rel,
                          "sha256": hashlib.sha256(
                              p.read_bytes()).hexdigest()},
               "parameters": a["parameters"], "unknown_calls": a["unknown_calls"]}
        apps[a["otb_name"].lower()] = rec

    out = {"pin": PIN, "n_apps_parsed": len(apps), "parse_failures": misses,
           "apps": apps}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    print("parsed:", len(apps), "apps ->", OUT.name)
    if misses:
        print("parse failures:", misses)
    if args.app:
        for name in args.app.split(","):
            rec = apps.get(name.strip().lower())
            if not rec:
                print(f"== {name}: NOT FOUND")
                continue
            print(f"\n== {rec['otb_name']}  ({rec['source']['path']})")
            print("   desc:", (rec["description"] or "")[:140])
            for p in rec["parameters"]:
                d = f" default={p['default']}" if p["default"] is not None else ""
                req = " REQUIRED" if p["required"] else ""
                ch = f" choices={len(p['choices'])}" if p["choices"] else ""
                print(f"   [{p['io_class']:6}] {p['key']}"
                      f" ({p['otb_type']}){req}{d}{ch}")


if __name__ == "__main__":
    main()
