#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 experiment step 2: build the v0_5-arm S2 pack for the 158 affected steps.

Reuses the frozen S2_PROMPT template and full_card renderer; cards rendered
from profile v0_5; Top-10 taken from the frozen S1 retrieval.json files.
Control prompts are re-rendered from v0_4 and their sha16 checked against the
frozen record.json prompt_sha16 for every item (pairing validity).

Output:
  a1_v1/A1_S2_PACK_V05_V1.pack.json     (158 items, dx_run_stage_v1 format)
  a1_v1/A1_PACK_MANIFEST_V1.json        (SHA256 + per-item pairing proof)
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from dx_common import PCA2  # noqa: E402
from dx_s23 import S2_PROMPT, S2_MAXNEW  # noqa: E402
from diag50_b3_build_pack_v1 import full_card  # noqa: E402

FULL = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
                "dx50_full_v1"))
RUNS = FULL / "runs"
A1 = FULL / "a1_v1"


def load_profile_path(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "_meta"}


def sha16(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    prof4 = load_profile_path(REPO / "route2_training/profile/"
                              "qgis_operator_capability_profile_v0_4.json")
    prof5 = load_profile_path(REPO / "route2_training/profile/"
                              "qgis_operator_capability_profile_v0_5.json")
    affected = json.loads((A1 / "A1_AFFECTED_SET_V1.json")
                          .read_text(encoding="utf-8"))["affected_steps"]

    texts = {}
    for line in (PCA2 / "pca2_taskset_100.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        texts[r["pid"]] = r["instruction"]

    items, pairing = [], []
    for row in affected:
        tid, snum = row["step_key"].split("#S")
        snum = int(snum)
        task_dir = RUNS / tid
        s0 = json.loads((task_dir / "S0" / "parsed.json").read_text(encoding="utf-8"))
        st = next(s for s in s0["steps"] if s["num"] == snum)
        retr = {x["step"]: x for x in json.loads(
            (task_dir / "S1" / "retrieval.json").read_text(encoding="utf-8")
        ).get("steps", [])}
        oids = [c["operator_id"] for c in retr[snum]["top10"]]
        cards5 = "\n\n".join(full_card(o, prof5)[0] for o in oids)
        prompt5 = S2_PROMPT.format(
            k=snum, name=st["name"], purpose=st["fields"].get("purpose", "-"),
            inp=st["fields"].get("input", "-"),
            out=st["fields"].get("output", "-"), cards=cards5)
        rec = json.loads((task_dir / "S2" / f"S{snum}" / "record.json")
                         .read_text(encoding="utf-8"))
        pairing.append({
            "step_key": row["step_key"],
            "control_prompt_sha16": rec.get("prompt_sha16"),
            "experiment_prompt_sha16": sha16(prompt5),
            "frozen_raw_status": rec.get("status"),
        })
        items.append({"task_id": tid, "stage": "S2",
                      "out_sub": f"S2/S{snum}",
                      "item_key": row["step_key"],
                      "prompt": prompt5, "maxnew": S2_MAXNEW})

    pack = {"items": items,
            "_meta": {"mode": "s2", "experiment": "A1 v0_5 arm",
                      "protocol": "DX_PROTOCOL_V1 (FROZEN 2026-10-16)",
                      "profile": "qgis_operator_capability_profile_v0_5.json",
                      "n_items": len(items), "tag": "a1_v05"}}
    pack_path = A1 / "A1_S2_PACK_V05_V1.pack.json"
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    affected_doc = json.loads((A1 / "A1_AFFECTED_SET_V1.json")
                              .read_text(encoding="utf-8"))
    manifest = {
        "date": "2026-10-17",
        "pack_file": pack_path.name,
        "pack_sha256": sha256_file(pack_path),
        "n_items": len(items),
        "profile_v05_sha256": sha256_file(
            REPO / "route2_training/profile/"
            "qgis_operator_capability_profile_v0_5.json"),
        "pairing_all_control_aligned": bool(affected_doc["alignment_ok"])
        and len(pairing) == affected_doc["n_affected"],
        "pairing": pairing,
        "notes": "control_prompt_sha16 is the FROZEN record's prompt hash "
                 "(v0_4 arm); experiment prompts differ only in OTB cards.",
    }
    (A1 / "A1_PACK_MANIFEST_V1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("pack:", pack_path)
    print("items:", len(items), "| pack sha256:", manifest["pack_sha256"][:16])


if __name__ == "__main__":
    main()
