#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A-track P0 OTB evidence extraction V2.

V2 extends V1 (scripts/dx_a_track_otb_extract_v1.py, frozen) with:
  - AUX_SOURCES: apps whose parameters live in base-class headers
    (otb:trainimagesclassifier / otb:trainvectorclassifier ->
     otbTrainImagesBase.hxx / otbTrainVectorBase.hxx + otbLearningApplicationBase.hxx
     + one hxx per classifier with AddChoice("classifier.<name>"...) and its
     sub-parameters). Parameters from aux files are merged by key; every
     parameter records `sources` (list of source files) per the owner constraint
     "per-field provenance".
  - COMPOSITE: otb:bundletoperfectsensor is an OTB CompositeApplication - its
    parameters are the union of the composed applications' parameters, exposed
    under "<instance>." key prefixes (AddApplication("Superimpose","superimpose",...)).

Same C++ macro grammar and output shape as V1; parameters additionally carry
`sources`. Output: otb_evidence_812_v2.json (V1 file stays frozen).
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OTB = REPO.parent / "_external_evidence/otb_upstream_v1"
APP_DIR = OTB / "Modules/Applications"
OUT = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
               "dx50_full_v1/a_track_p0_v1/otb_evidence_812_v2.json"))

PIN = {"tag": "8.1.2", "commit": "b3eb56034e371846c39ae249f837b6c14b3b5039",
       "mirror": "https://github.com/orfeotoolbox/OTB",
       "layout": "Modules/Applications/App<Name>/app/otb<Name>.cxx "
                 "(+ include/*.hxx aux sources for composite/base-class apps)"}

CLS = APP_DIR / "AppClassification/include"
AUX_SOURCES = {
    "trainimagesclassifier": [
        CLS / "otbTrainImagesBase.hxx",
        CLS / "otbLearningApplicationBase.hxx",
        CLS / "otbTrainLibSVM.hxx", CLS / "otbTrainSVM.hxx",
        CLS / "otbTrainBoost.hxx", CLS / "otbTrainDecisionTree.hxx",
        CLS / "otbTrainKNN.hxx", CLS / "otbTrainNeuralNetwork.hxx",
        CLS / "otbTrainNormalBayes.hxx", CLS / "otbTrainRandomForests.hxx",
        CLS / "otbTrainSharkKMeans.hxx", CLS / "otbTrainSharkRandomForests.hxx",
    ],
    "trainvectorclassifier": [
        CLS / "otbTrainVectorBase.hxx",
        CLS / "otbLearningApplicationBase.hxx",
        CLS / "otbTrainLibSVM.hxx", CLS / "otbTrainSVM.hxx",
        CLS / "otbTrainBoost.hxx", CLS / "otbTrainDecisionTree.hxx",
        CLS / "otbTrainKNN.hxx", CLS / "otbTrainNeuralNetwork.hxx",
        CLS / "otbTrainNormalBayes.hxx", CLS / "otbTrainRandomForests.hxx",
        CLS / "otbTrainSharkKMeans.hxx", CLS / "otbTrainSharkRandomForests.hxx",
    ],
}
COMPOSITE = {"bundletoperfectsensor": [("superimpose", "superimpose"),
                                       ("pansharp", "pansharpening")]}

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
    r"SetParameterFloat|SetParameterDouble|SetName|SetDescription|"
    r"AddApplication|ShareParameter)\s*\(")
LITS_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def read_calls(text):
    out = []
    for m in CALL_RE.finditer(text):
        # skip object-level calls (GetInternalApplication("x")->SetParameter...,
        # obj.SetParameter...) - they do not define THIS application's params;
        # but `this->Foo()` / `this.Foo()` DOES belong to this application
        k = m.start() - 1
        while k >= 0 and text[k] in " \t":
            k -= 1  # same-line whitespace only: a receiver never spans lines
        if k >= 0 and text[k] in ".>":
            j = k - 1
            is_arrow = text[k] == ">" and j >= 0 and text[j] == "-"
            if is_arrow:
                j -= 1  # '->' arrow: skip the hyphen before walking the receiver
            while j >= 0 and (text[j].isalnum() or text[j] == "_"):
                j -= 1
            recv_end = k - 1 if is_arrow else k
            if text[j + 1:recv_end] != "this":
                continue
        i = m.end()
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
            parsed.append("".join(lits) if lits else a.strip())
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


class AppAcc:
    def __init__(self):
        self.otb_name = None
        self.description = None
        self.params = {}
        self.order = []
        self.composed_apps = []
        self.share_requests = []   # (newkey, internal_path, desc, src_rel)
        self.unknown_calls = 0

    def merge_param(self, key, item, src):
        if key in self.params:
            p = self.params[key]
            if src not in p["sources"]:
                p["sources"].append(src)
            p["required"] = p["required"] or item["required"]
            if p["default"] is None and item["default"] is not None:
                p["default"] = item["default"]
            if not p["description"] and item["description"]:
                p["description"] = item["description"]
            for ck, cv in item["choices"].items():
                p["choices"].setdefault(ck, cv)
        else:
            self.params[key] = item
            self.order.append(key)

    def add_param(self, ptype, key, human, src):
        io, norm = classify(ptype)
        self.merge_param(key, {
            "key": key, "human_name": human, "otb_type": ptype,
            "io_class": io, "normalized_type": norm,
            "required": False, "default": None, "description": None,
            "choices": {}, "sources": [src]}, src)

    def to_record(self):
        return {"otb_name": self.otb_name, "description": self.description,
                "parameters": [self.params[k] for k in self.order],
                "composed_apps": self.composed_apps,
                "unknown_calls": self.unknown_calls}


def parse_source(text, src_rel, acc):
    for fn, args in read_calls(text):
        try:
            if fn == "SetName" and acc.otb_name is None:
                acc.otb_name = args[0]
            elif fn == "SetDescription" and acc.description is None:
                acc.description = unescape(args[0])
            elif fn == "AddParameter" and len(args) >= 3:
                acc.add_param(re.sub(r"^ParameterType_", "", str(args[0])),
                              args[1], args[2], src_rel)
            elif fn == "AddChoice" and len(args) >= 2:
                key, label = args[0], args[1]
                parent = key.rsplit(".", 1)[0]
                if parent in acc.params:
                    acc.params[parent]["choices"][key] = {
                        "label": label, "description": None}
            elif fn == "SetParameterDescription" and len(args) >= 2:
                key, desc = args[0], unescape(args[1])
                if key in acc.params:
                    if not acc.params[key]["description"]:
                        acc.params[key]["description"] = desc
                elif "." in key:
                    parent = key.rsplit(".", 1)[0]
                    if parent in acc.params and \
                            key in acc.params[parent]["choices"]:
                        acc.params[parent]["choices"][key]["description"] = desc
            elif fn == "MandatoryOn" and args and args[0] in acc.params:
                acc.params[args[0]]["required"] = True
            elif fn == "MandatoryOff" and args and args[0] in acc.params:
                acc.params[args[0]]["required"] = False
            elif fn in ("SetParameterString", "SetParameterInt",
                        "SetParameterFloat", "SetParameterDouble",
                        "SetDefaultParameterInt", "SetDefaultParameterFloat",
                        "SetDefaultParameterDouble") and len(args) >= 2:
                if args[0] in acc.params and \
                        acc.params[args[0]]["default"] is None:
                    acc.params[args[0]]["default"] = args[1]
            elif fn == "SetParameterStringList" and len(args) >= 2:
                if args[0] in acc.params and \
                        acc.params[args[0]]["default"] is None:
                    acc.params[args[0]]["default"] = args[1:]
            elif fn == "AddApplication" and len(args) >= 2:
                acc.composed_apps.append({"app": args[0], "instance": args[1],
                                          "description": args[2] if len(args) > 2 else None})
            elif fn == "ShareParameter" and len(args) >= 2:
                acc.share_requests.append(
                    (args[0], args[1], unescape(args[2]) if len(args) > 2 else None,
                     src_rel))
        except (IndexError, KeyError):
            acc.unknown_calls += 1
    return acc


def resolve_shares(acc, accs):
    """Resolve ShareParameter(newkey, "instance.param.path") against the
    composed application bindings; fall back to an explicit unresolved
    SharedParameter placeholder (no guessing)."""
    for newkey, internal_path, desc, src_rel in acc.share_requests:
        if newkey in acc.params:
            acc.params[newkey]["sources"].append(f"shared: {internal_path}")
            if desc and not acc.params[newkey]["description"]:
                acc.params[newkey]["description"] = desc
            continue
        parts = internal_path.split(".", 1)
        if len(parts) != 2:
            acc.unknown_calls += 1
            continue
        instance, rest = parts
        binding = next((c for c in acc.composed_apps
                        if c["instance"] == instance), None)
        src_acc = accs.get(binding["app"].lower()) if binding else None
        src_p = src_acc.params.get(rest) if src_acc else None
        if src_p is not None and src_p["io_class"] == "section":
            # sharing a Group exposes the whole prefixed subtree
            for k2, p2 in src_acc.params.items():
                if k2 == rest or k2.startswith(rest + "."):
                    item = dict(p2)
                    item["sources"] = [f"shared from {binding['app']}.{k2} "
                                       f"via {src_rel}"]
                    acc.merge_param(k2, item, src_rel)
            continue
        if src_p is None:
            acc.merge_param(newkey, {
                "key": newkey, "human_name": None, "otb_type": "SharedParameter",
                "io_class": "unknown", "normalized_type": "unknown",
                "required": False, "default": None, "description": desc,
                "choices": {},
                "sources": [f"unresolved share: {internal_path} ({src_rel})"]},
                src_rel)
            continue
        item = dict(src_p)
        item["key"] = newkey
        item["sources"] = [f"shared from {binding['app']}.{rest} via {src_rel}"]
        if desc:
            item["description"] = desc
        acc.merge_param(newkey, item, src_rel)


def parse_composite(name, acc, apps_by_name, src_registry):
    """Prefix composed apps' parameters with the instance name."""
    for comp in acc.composed_apps:
        src_app = apps_by_name.get(comp["app"].lower())
        if src_app is None:
            acc.unknown_calls += 1
            continue
        prefix = comp["instance"] + "."
        for p in src_app["parameters"]:
            if p["io_class"] == "section":
                continue
            item = dict(p)
            item["key"] = prefix + p["key"]
            item["sources"] = [f"{comp['app']} via {s}" for s in p["sources"]]
            acc.merge_param(item["key"], item, src_registry)
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=None,
                    help="comma-separated SetName filter for a pilot run")
    args = ap.parse_args()

    files = sorted(p for p in APP_DIR.glob("App*/app/otb*.cxx")
                   if "/test/" not in str(p).replace("\\", "/").lower())
    accs, misses = {}, []
    for p in files:
        rel = p.relative_to(OTB).as_posix()
        acc = parse_source(p.read_text(encoding="utf-8", errors="replace"),
                           rel, AppAcc())
        name_l = (acc.otb_name or "").lower()
        for aux in AUX_SOURCES.get(name_l, []):
            if aux.exists():
                parse_source(aux.read_text(encoding="utf-8", errors="replace"),
                             aux.relative_to(OTB).as_posix(), acc)
            else:
                misses.append(f"aux missing: {aux}")
        accs[name_l] = acc

    # resolve ShareParameter exposes after all apps are parsed
    for acc in accs.values():
        resolve_shares(acc, accs)

    # resolve composites after all apps are parsed
    apps_by_name = {n: a.to_record() for n, a in accs.items()}
    for name_l, comps in COMPOSITE.items():
        acc = accs[name_l]
        parse_composite(name_l, acc, apps_by_name, "composed app")

    apps, final_misses = {}, list(misses)
    for n, acc in accs.items():
        rec = acc.to_record()
        if not rec["otb_name"]:
            final_misses.append(n)
            continue
        main_src = [p["sources"][0] for p in rec["parameters"][:1]]
        rec["source_files"] = sorted({s for p in rec["parameters"]
                                      for s in p["sources"]})
        apps[n] = rec

    out = {"pin": PIN, "extractor": "dx_a_track_otb_extract_v2.py",
           "n_apps_parsed": len(apps), "parse_failures": final_misses,
           "aux_sources": {k: [str(p.relative_to(OTB).as_posix())
                               for p in v] for k, v in AUX_SOURCES.items()},
           "composite": {k: v for k, v in COMPOSITE.items()},
           "apps": apps}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    print("parsed:", len(apps), "apps ->", OUT.name)
    if final_misses:
        print("misses:", final_misses)
    if args.app:
        for name in args.app.split(","):
            rec = apps.get(name.strip().lower())
            if not rec:
                print(f"== {name}: NOT FOUND")
                continue
            print(f"\n== {rec['otb_name']}  "
                  f"({len(rec['parameters'])} params, "
                  f"{len(rec['source_files'])} source files)")
            print("   desc:", (rec["description"] or "")[:120])
            for p in rec["parameters"][:40]:
                d = f" default={p['default']}" if p["default"] is not None else ""
                req = " REQUIRED" if p["required"] else ""
                ch = f" choices={len(p['choices'])}" if p["choices"] else ""
                print(f"   [{p['io_class']:6}] {p['key']}"
                      f" ({p['otb_type']}){req}{d}{ch}")


if __name__ == "__main__":
    main()
