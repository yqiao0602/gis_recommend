#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a vector L3 training set from the complete QGIS samples (chain+description).

Takes qgis_complete_*.jsonl (script, task_type, task_name, task_description, chain,
modality) — the join of yll's extracted chains with facts_summary descriptions —
maps each alg-id chain -> L3 codes via the SAME crosswalk/id_mappings path that
produced the local seed (build_qgis_chain_dataset.map_to_l3, strict all-or-nothing),
keeps real task_type (if in the 47-vocab, else 'Other / Sparse') + real
description, filters by length, and emits labeled_workflows-schema training
samples (description -> L3).

Usage:
    python scripts/build_vector_training_set_v2.py \
        --complete outputs_v2/diagnostics/qgis_complete_ALL.jsonl \
        --out outputs_v2/vector_training_samples_v2.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_qgis_chain_dataset import (  # noqa: E402  (authoritative mapping, reused for L3 parity)
    load_official_qgis_operators,
    load_alg_id_crosswalk,
    build_l3_lookup,
    map_to_l3,
    OFFICIAL_OPS_PATH,
)
from gis_recommend.data.vector_training_builder import to_training_sample  # noqa: E402

OUT_DIR = ROOT / "outputs_v2"
STEP8 = OUT_DIR / "pipeline" / "step8_quality_gate"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--complete", type=Path, default=OUT_DIR / "diagnostics" / "qgis_complete_ALL.jsonl")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "vector_training_samples_v2.jsonl")
    ap.add_argument("--min-len", type=int, default=2)
    ap.add_argument("--max-len", type=int, default=12)
    args = ap.parse_args()

    catalog = load_official_qgis_operators(OFFICIAL_OPS_PATH)
    crosswalk = load_alg_id_crosswalk(OUT_DIR / "qgis_alg_id_crosswalk_expanded.json")
    l3_lookup = build_l3_lookup(OUT_DIR / "id_mappings_v2.json")
    vocab = json.loads((OUT_DIR / "l3_vocab_v2.json").read_text(encoding="utf-8"))
    code_to_id, special = vocab["code_to_id"], vocab["special_tokens"]
    tt2id = json.loads((STEP8 / "task_type_vocabulary_v4_quality_gate.json").read_text(encoding="utf-8"))["task_type_to_id"]
    print(f"catalog={len(catalog)} crosswalk={len(crosswalk)} l3_lookup={len(l3_lookup)} l3_vocab={len(code_to_id)} task_types={len(tt2id)}")

    st = Counter()
    samples = []
    tt_dist = Counter()
    with open(args.complete, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            st["in"] += 1
            rec = json.loads(line)
            chain = rec.get("chain", [])
            desc = (rec.get("task_description") or "").strip()
            if not desc:
                st["no_desc"] += 1
                continue
            l3_codes = map_to_l3(chain, catalog, l3_lookup, crosswalk)
            if l3_codes is None:
                st["unmappable"] += 1
                continue
            if not (args.min_len <= len(l3_codes) <= args.max_len):
                st["len_filtered"] += 1
                continue
            tt = rec.get("task_type", "") if rec.get("task_type", "") in tt2id else "Other / Sparse"
            described = {
                "optional_l3_sequence": l3_codes,
                "task_description_en": desc,
                "qgis_ops": chain,
                "operator_names": [],
                "source": f"qgis_yll_{rec.get('modality', 'na')}",
            }
            ts = to_training_sample(described, code_to_id=code_to_id, special_tokens=special,
                                    task_type=tt, task_type_to_id=tt2id)
            if ts is None:
                st["l3_oov"] += 1
                continue
            if rec.get("task_name"):
                ts["task_metadata"]["task_name"] = rec["task_name"]  # keep the real extracted name
            ts["modality"] = rec.get("modality", "")
            samples.append(ts)
            st["kept"] += 1
            tt_dist[tt] += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    mod = Counter(s["modality"] for s in samples)
    print(f"\nin={st['in']}  unmappable={st['unmappable']}  len_filtered={st['len_filtered']}  "
          f"l3_oov={st['l3_oov']}  no_desc={st['no_desc']}  KEPT={st['kept']}")
    print(f"mapped_rate={st['kept']/max(st['in'],1):.1%}")
    print(f"modality: {dict(mod)}  vector-relevant={mod['vector']+mod['mixed']}")
    print(f"task_type top: {tt_dist.most_common(8)}")
    print(f"out -> {args.out}")
    if samples:
        ex = samples[0]
        print(f"\nexample: [{ex['task_metadata']['task_type']}] {ex['task_metadata']['task_name']}")
        print(f"  desc: {ex['task_metadata']['task_description'][:140]}")
        print(f"  L3: {' -> '.join(c for c in ex['l3_codes'] if not c.startswith('<'))}")


if __name__ == "__main__":
    main()
