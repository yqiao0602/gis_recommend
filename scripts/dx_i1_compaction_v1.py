#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""I1 prep: field-importance audit + deterministic compaction prototype (NO generation).

Owner conditions (2026-10-18):
  - never delete decision-relevant evidence; blind 'first 8 optional' rejected;
  - deterministic compression of redundancy only; over-budget cards are flagged,
    not further stripped;
  - token statistics (not just char cap) must prove the prompt got shorter;
  - paired run must regenerate BOTH arms in the same round (A1 only historical).

Classification rule (explicit, auditable):
  SEMANTIC (kept with name+type): all required params; every Choice; every
    input/output class (raster/vector/file/model/field); Bool flags; Field;
    params whose name matches SEM_NAMES (mask/nodata/threshold/method/mode/
    type/level/sensor/filter/band/class/layer/field/feat/model/lut/stats/
    training/roi/table/grid/source/input/output).
  EXECUTION (summarised as a count): Int/Float/number tuning knobs whose names
    match EXEC_NAMES or the OTB classifier sub-parameter families
    (classifier.*.{k,m,c,gamma,nu,degree,coef0,eps,term,iter,p,opt,prob,ra,
    cat,var,max,min}), plus generic run-time knobs.
  UNKNOWN: anything else -> treated as SEMANTIC (fail-safe: keep).
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHORT = REPO.parent
V05 = REPO / "route2_training/profile/qgis_operator_capability_profile_v0_5.json"
A1 = SHORT / "a1_short"
CTRL_TREE = SHORT / "dx50_short/runs"
WORK = SHORT / "_i1_prep_work"
OUT = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
               "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
               "dx50_full_v1/i1_v1"))
CHAR_BUDGET = 1200

SEM_NAMES = re.compile(
    r"(mask|nodata|no_data|threshold|method|mode|type|level|sensor|filter|"
    r"band|class|layer|field|feat|model|lut|stats|training|roi|table|grid|"
    r"source|input|output|strategy|interpolator|resampl)", re.I)
EXEC_NAMES = re.compile(
    r"(radius|size|width|height|iter|maxit|iteration|eps|epsilon|tol|tolerance|"
    r"memory|ram|tile|block|cores|threads|verbose|seed|buffer|spacing|"
    r"resolution|cleanup|tmpdir|smooth|scale|factor|nskip|bins|hfact|milli|"
    r"clamp|cell_count|cell_size|spacingx|spacingy|clean|delete)", re.I)
CLASSIFIER_SUB = re.compile(
    r"^classifier\.[a-z0-9]+\.(k|m|c|gamma|nu|degree|coef0|eps|term|iter|p|"
    r"opt|prob|ra|cat|var|max|min|maxdepth|mindepth)$", re.I)


def load_prof():
    d = json.loads(V05.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "_meta"}


def classify_param(p):
    if p.get("mandatory"):
        return "required"
    if p.get("choices"):
        return "semantic"
    name, typ = p.get("name", ""), p.get("type", "")
    if CLASSIFIER_SUB.match(name):
        return "execution"
    if typ in ("Choice", "Field", "Bool", "Bool", "String", "string",
               "InputImage", "InputImageList", "InputVectorData",
               "InputVectorDataList", "InputFilename", "raster", "vector",
               "source", "multilayer", "extent", "file", "sink", "mesh"):
        return "semantic"
    if SEM_NAMES.search(name):
        return "semantic"
    if typ in ("Int", "Float", "number") and EXEC_NAMES.search(name):
        return "execution"
    if typ in ("Int", "Float", "number"):
        return "semantic"          # fail-safe: a numeric knob we cannot rule out
    if typ == "literal":
        return "semantic"          # GRASS7 literals often are IO names
    return "semantic"


def compact_card(oid, prof):
    e = prof.get(oid) or {}
    lb = e.get("layer_b_params") or {}
    params = lb.get("parameters") or []
    req = [p for p in params if classify_param(p) == "required"]
    sem = [p for p in params if classify_param(p) == "semantic"]
    exe = [p for p in params if classify_param(p) == "execution"]
    lines = [f"### {oid}  [{e.get('provider', '?')}] {e.get('official_name', '?')}"]
    lines.append("accepts: " + (", ".join(e.get("input_types_norm") or ["none documented"])))
    outs = lb.get("outputs") or []
    lines.append("outputs: " + (("; ".join(f"{o['name']}({o['type']})" for o in outs)
                                if outs else "none documented")))
    seg = "; ".join(f"{p['name']}({p['type']}, required, default={p.get('default')})"
                    for p in req) or "none required"
    opt = "; ".join(f"{p['name']}({p['type']})" for p in sem)
    tail = f" || optional({len(sem) + len(exe)}): {opt}" if opt else ""
    if exe:
        tail += f"; (+{len(exe)} execution params)"
    lines.append(f"params: {seg}{tail}")
    it = (e.get("layer_c_intent") or {}).get("text")
    if it:
        lines.append(f"description: {it}")
    card = "\n".join(lines)
    over = len(card) > CHAR_BUDGET
    if over:
        card += f"\n[over_budget: {len(card)} chars; NOT truncated further]"
    return card, {"required": len(req), "semantic_optional": len(sem),
                  "execution_omitted": len(exe), "over_budget": over,
                  "omitted_names": [p["name"] for p in exe]}


def main():
    from importlib import import_module
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    full_card = import_module("diag50_b3_build_pack_v1").full_card
    from dx_s23 import S2_PROMPT

    prof = load_prof()
    affected = {r["step_key"]: r for r in json.loads(
        (A1 / "A1_AFFECTED_SET_V1.json").read_text(encoding="utf-8"))["affected_steps"]}
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    audit = defaultdict(Counter)
    for oid, e in prof.items():
        if not (e.get("layer_b_params") or {}).get("parameters"):
            continue
        for p in e["layer_b_params"]["parameters"]:
            audit[oid][classify_param(p)] += 1

    prompts, card_stats = [], []
    for key in sorted(affected):
        tid, snum = key.split("#S")
        snum = int(snum)
        s0 = json.loads((CTRL_TREE / tid / "S0" / "parsed.json").read_text(encoding="utf-8"))
        step = next(x for x in s0["steps"] if x["num"] == snum)
        retr = {x["step"]: x for x in json.loads(
            (CTRL_TREE / tid / "S1" / "retrieval.json").read_text(encoding="utf-8")).get("steps", [])}
        oids = [c["operator_id"] for c in retr[snum]["top10"]]
        fmt = dict(k=snum, name=step["name"],
                   purpose=step["fields"].get("purpose", "-"),
                   inp=step["fields"].get("input", "-"),
                   out=step["fields"].get("output", "-"))
        ctl_cards = "\n\n".join(full_card(o, prof)[0] for o in oids)
        comp_cards, meta = [], []
        for o in oids:
            c, m = compact_card(o, prof)
            comp_cards.append(c)
            meta.append({"oid": o, **m})
        prompts.append({"key": key, "arm": "control",
                        "prompt": S2_PROMPT.format(cards=ctl_cards, **fmt)})
        prompts.append({"key": key, "arm": "compacted",
                        "prompt": S2_PROMPT.format(cards="\n\n".join(comp_cards), **fmt)})
        card_stats.append({"step_key": key,
                           "control_chars": len(ctl_cards),
                           "compacted_chars": len("\n\n".join(comp_cards)),
                           "cards": meta})
    (WORK / "i1_prompts.json").write_text(json.dumps(prompts, ensure_ascii=False),
                                          encoding="utf-8")
    (OUT / "I1_FIELD_IMPORTANCE_AUDIT_V1.json").write_text(
        json.dumps({"rule": "see docstring; UNKNOWN->semantic (fail-safe)",
                    "per_operator": {k: dict(v) for k, v in audit.items()},
                    "totals": dict(sum((Counter(v) for v in audit.values()), Counter()))},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "I1_CARD_STATS_V1.json").write_text(
        json.dumps({"char_budget": CHAR_BUDGET, "steps": card_stats,
                    "over_budget_cards": sum(1 for s in card_stats
                                             for c in s["cards"] if c["over_budget"])},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("prompts:", len(prompts), "| audit operators:", len(audit))
    print("totals:", dict(sum((Counter(v) for v in audit.values()), Counter())))
    print("over-budget cards:", sum(1 for s in card_stats for c in s["cards"] if c["over_budget"]))
    import statistics
    cr = [s["compacted_chars"] / s["control_chars"] for s in card_stats]
    print("char ratio compact/control: median", round(statistics.median(cr), 3),
          "min", round(min(cr), 3), "max", round(max(cr), 3))


if __name__ == "__main__":
    main()
