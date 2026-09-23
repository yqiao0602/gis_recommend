#!/usr/bin/env python3
"""FA-D2/D3: semantic projection + FP decomposition over locked test-111
predictions (CPU, offline, deterministic; bootstrap rng frozen 20260923).

D2: project predicted & gold operators to semantic classes (fa_semantic_map_v1),
    compute projected op/link multiset F1 per row; bootstrap CI on A1-C0 and
    B1-C0 deltas. Readout (pre-registered): CI<0 -> Planning damaged;
    CI contains 0 -> Planning preserved.
D3: decompose each arm's false-positive operator instances (multiset
    pred-minus-gold, Protocol v2 accounting) into SAME-FAMILY (projected class
    belongs to the row's gold class set = grounding failure) vs
    OUT-OF-FAMILY (class absent from gold = generation-control failure).
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route2_training.harness import text_to_graph  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MAP = json.loads((REPO / "scripts" / "fa_semantic_map_v1.json").read_text(encoding="utf-8"))
CLASS_OF = {op: v["class"] for op, v in MAP["mapping"].items()}
RNG_SEED = 20260923
N_BOOT = 10000


def cls_of(op):
    return CLASS_OF.get(op, "OTHER_UNMAPPED")


def parse_pred(raw):
    for line in (raw or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            procs, links = text_to_graph(line)
            return procs, links
        except ValueError:
            continue
    return [], []


def load_rows():
    gold = {}
    for line in (REPO / "docs/reports/v2a_manifest/v2a_A_test.jsonl").read_text(
            encoding="utf-8").splitlines():
        r = json.loads(line)
        gold[r["wid"]] = r
    arms = {}
    for arm, f in (("C0", "C0_ep20"), ("A1", "A1_ep15"), ("B1", "B1_ep18")):
        rows = {}
        for line in (REPO / f"docs/reports/route2_p0_contract/test111_final_v1/{f}_predictions.jsonl").read_text(
                encoding="utf-8").splitlines():
            r = json.loads(line)
            procs, links = parse_pred(r.get("raw_generation", ""))
            rows[r["wid"]] = (procs, links)
        arms[arm] = rows
    return gold, arms


def projected_f1(pred_ops, gold_ops):
    pc = Counter(cls_of(o) for o in pred_ops)
    gc = Counter(cls_of(o) for o in gold_ops)
    inter = sum((pc & gc).values())
    tot = sum(pc.values()) + sum(gc.values())
    return (2 * inter / tot) if tot else 0.0


def projected_link_f1(pred_procs, pred_links, gold_procs, gold_links):
    pc = {p["process_id"]: cls_of(p["operator_id"]) for p in pred_procs}
    gc = {p["process_id"]: cls_of(p["operator_id"]) for p in gold_procs}
    pl = Counter(tuple(sorted((pc.get(l["source_process_id"], "?"),
                               pc.get(l["target_process_id"], "?")))) for l in pred_links)
    gl = Counter(tuple(sorted((gc.get(l["source_process_id"], "?"),
                               gc.get(l["target_process_id"], "?")))) for l in gold_links)
    inter = sum((pl & gl).values())
    tot = sum(pl.values()) + sum(gl.values())
    return (2 * inter / tot) if tot else 0.0


def main() -> int:
    gold, arms = load_rows()
    wids = sorted(gold)

    per_row = {a: {"proj_op": {}, "proj_link": {}} for a in arms}
    fp = {a: {"same": Counter(), "out": Counter(), "same_n": 0, "out_n": 0} for a in arms}
    confusions = {a: Counter() for a in arms}

    for wid in wids:
        g = gold[wid]
        g_ops = [p["operator_id"] for p in g["processes"]]
        g_cls = set(cls_of(o) for o in g_ops)
        for arm, rows in arms.items():
            procs, links = rows[wid]
            p_ops = [p["operator_id"] for p in procs]
            per_row[arm]["proj_op"][wid] = projected_f1(p_ops, g_ops)
            per_row[arm]["proj_link"][wid] = projected_link_f1(procs, links,
                                                               g["processes"], g["links"])
            # FP decomposition (multiset pred minus gold, Protocol v2 style)
            pc, gc = Counter(p_ops), Counter(g_ops)
            for op, n in (pc - gc).items():
                c = cls_of(op)
                if c in g_cls:
                    fp[arm]["same"][op] += n
                    fp[arm]["same_n"] += n
                else:
                    fp[arm]["out"][op] += n
                    fp[arm]["out_n"] += n
                    confusions[arm][op] += n

    res = {"schema": "gis_recommend.transfer.fa.d2d3", "n_rows": len(wids),
           "n_boot": N_BOOT, "map_coverage": MAP["coverage_rate"]}

    # D2 aggregates + bootstrap
    def mean(v):
        return sum(v) / len(v)
    for metric in ("proj_op", "proj_link"):
        res[metric] = {a: round(mean(list(per_row[a][metric].values())), 4) for a in arms}
    rng = random.Random(RNG_SEED)
    for pair in (("A1", "C0"), ("B1", "C0"), ("B1", "A1")):
        for metric in ("proj_op", "proj_link"):
            fa, fb = per_row[pair[0]][metric], per_row[pair[1]][metric]
            deltas = []
            for _ in range(N_BOOT):
                s = [wids[rng.randrange(len(wids))] for _ in wids]
                deltas.append(mean([fa[w] - fb[w] for w in s]))
            deltas.sort()
            res.setdefault("bootstrap_ci", {})[f"{pair[0]}-{pair[1]}_{metric}"] = [
                round(mean([fa[w] - fb[w] for w in wids]), 4),
                round(deltas[int(0.025 * N_BOOT)], 4), round(deltas[int(0.975 * N_BOOT)], 4)]

    # D3 decomposition
    for a in arms:
        tot = fp[a]["same_n"] + fp[a]["out_n"]
        res.setdefault("fp_decomp", {})[a] = {
            "fp_total": tot, "same_family": fp[a]["same_n"],
            "out_of_family": fp[a]["out_n"],
            "out_share": round(fp[a]["out_n"] / max(tot, 1), 4),
            "top_out": fp[a]["out"].most_common(10),
            "top_same": fp[a]["same"].most_common(10)}
    rng2 = random.Random(RNG_SEED + 1)

    # bootstrap on out-share difference A1-C0 (row resample, recompute shares)
    def arm_out_share(arm, wids_subset):
        same = out_n = 0
        for wid in wids_subset:
            g = gold[wid]
            g_cls = set(cls_of(p["operator_id"]) for p in g["processes"])
            pc = Counter(p["operator_id"] for p in arms[arm][wid][0])
            gc = Counter(p["operator_id"] for p in g["processes"])
            for op, n in (pc - gc).items():
                if cls_of(op) in g_cls:
                    same += n
                else:
                    out_n += n
        return out_n / max(same + out_n, 1)
    deltas = []
    for _ in range(N_BOOT):
        s = [wids[rng2.randrange(len(wids))] for _ in wids]
        deltas.append(arm_out_share("A1", s) - arm_out_share("C0", s))
    deltas.sort()
    point = arm_out_share("A1", wids) - arm_out_share("C0", wids)
    res["fp_decomp"]["A1-C0_out_share_delta"] = {
        "point": round(point, 4), "ci95": [round(deltas[int(0.025 * N_BOOT)], 4),
                                           round(deltas[int(0.975 * N_BOOT)], 4)]}

    dest = REPO / "docs/reports/transfer_phase2/fa/fa_d2_d3_results.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
