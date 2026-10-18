#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 (owner priority): enum-expansion probe.

Question: when the frozen card renderer is augmented to PRINT the choice
values that already exist in profile v0_5 (classifier -> libsvm/svm/boost/dt/
knn/ann/bayes/rf/sharkkm/sharkrf, etc.), do the S2 decisions on the three
named steps change?

Design (single variable):
  control    = A1 v0_5 arm runs (frozen; prompt re-rendered and sha16-checked)
  experiment = same steps/Top-10/template/model/decode, cards rendered with an
               ADDITIVE "choices:" line per choice parameter.
Scope: PCA2-T-009#S4, PCA2-T-009#S6, PCA2-T-056#S6 (owner-named).
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_s23 import S2_PROMPT, S2_MAXNEW  # noqa: E402
from diag50_b3_build_pack_v1 import full_card  # noqa: E402

SHORT = REPO.parent  # Algorithm_classification/
A1 = SHORT / "a1_short"
A1_CTRL = SHORT / "_a1_work" / "runs_local"
CTRL_TREE = SHORT / "dx50_short" / "runs"
V05 = REPO / "route2_training/profile/qgis_operator_capability_profile_v0_5.json"
OUT = SHORT / "_p2_enum_work"
STEPS = ["PCA2-T-009#S4", "PCA2-T-009#S6", "PCA2-T-056#S6"]


def load_prof():
    d = json.loads(V05.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "_meta"}


def enum_card(oid, prof, max_choices=14):
    base = full_card(oid, prof)[0]
    e = prof.get(oid) or {}
    params = (e.get("layer_b_params") or {}).get("parameters") or []
    lines = []
    for q in params:
        ch = q.get("choices") or []
        if not ch:
            continue
        keys = [c["key"] for c in ch]
        if len(keys) > max_choices:
            keys = keys[:max_choices] + [f"...(+{len(ch) - max_choices})"]
        lines.append(f"  {q['name']}: {', '.join(keys)}")
    if lines:
        base += "\nchoice values:\n" + "\n".join(lines)
    return base


def sha16(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def main():
    prof = load_prof()
    affected = {r["step_key"]: r for r in json.loads(
        (A1 / "A1_AFFECTED_SET_V1.json").read_text(encoding="utf-8")
    )["affected_steps"]}

    OUT.mkdir(parents=True, exist_ok=True)
    items, align = [], []
    for key in STEPS:
        tid, snum = key.split("#S")
        snum = int(snum)
        s0 = json.loads((CTRL_TREE / tid / "S0" / "parsed.json")
                        .read_text(encoding="utf-8"))
        st = next(x for x in s0["steps"] if x["num"] == snum)
        retr = {x["step"]: x for x in json.loads(
            (CTRL_TREE / tid / "S1" / "retrieval.json").read_text(
                encoding="utf-8")).get("steps", [])}
        oids = [c["operator_id"] for c in retr[snum]["top10"]]

        cards_v05 = "\n\n".join(full_card(o, prof)[0] for o in oids)
        cards_enum = "\n\n".join(enum_card(o, prof) for o in oids)
        fmt = dict(k=snum, name=st["name"],
                   purpose=st["fields"].get("purpose", "-"),
                   inp=st["fields"].get("input", "-"),
                   out=st["fields"].get("output", "-"))
        p_ctrl = S2_PROMPT.format(cards=cards_v05, **fmt)
        p_exp = S2_PROMPT.format(cards=cards_enum, **fmt)

        # alignment proof against the A1 v0_5 arm
        rec = json.loads((A1_CTRL / tid / "S2" / f"S{snum}" / "gen.json")
                         .read_text(encoding="utf-8"))
        align.append({"step_key": key,
                      "control_prompt_sha16": sha16(p_ctrl),
                      "a1_record_prompt_sha16": rec.get("prompt_sha16"),
                      "aligned": sha16(p_ctrl) == rec.get("prompt_sha16"),
                      "experiment_prompt_sha16": sha16(p_exp),
                      "cards_changed_by_enum": sum(
                          1 for o in oids if enum_card(o, prof)
                          != full_card(o, prof)[0])})
        items.append({"task_id": tid, "stage": "S2", "out_sub": f"S2/S{snum}",
                      "item_key": key, "prompt": p_exp, "maxnew": S2_MAXNEW})

    pack = {"items": items,
            "_meta": {"mode": "s2", "experiment": "P1 enum expansion probe",
                      "protocol": "DX_PROTOCOL_V1 (FROZEN 2026-10-16)",
                      "profile": "qgis_operator_capability_profile_v0_5.json",
                      "treatment": "additive 'choice values:' lines from "
                                   "layer_b_params[].choices (renderer unchanged "
                                   "for control)", "n_items": len(items)}}
    pp = OUT / "P2_ENUM_PROBE_V1.pack.json"
    pp.write_text(json.dumps(pack, ensure_ascii=False, indent=1),
                  encoding="utf-8")
    manifest = {"steps": STEPS, "pack": pp.name,
                "pack_sha256": hashlib.sha256(pp.read_bytes()).hexdigest(),
                "alignment": align,
                "alignment_ok": all(a["aligned"] for a in align)}
    (OUT / "P2_ENUM_PROBE_MANIFEST_V1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
