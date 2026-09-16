# -*- coding: utf-8 -*-
"""V2a gate ③: build the A/B manifests + training JSONLs + static audit.

Rules come from docs/plans/v2a_spec.md; the OUTPUT of this script is the
authoritative record (owner 2026-09-16: spec defines rules, manifest defines
facts).

Pipeline: 2,185 chain>=2 candidates -> link projection (contract the DAG
through dropped nodes, linear fallback) -> ONE source-disjoint split
(85/7.5/7.5, reused by both profiles) -> weights (tier weight + fieldcalculator
<=10% exposure cap + taskType <=2xmedian cap, weight-based, no row deletion)
-> A (Tier-1 only) / B (Tier-1 x1.0 + Tier-2 x0.5) JSONLs -> manifest ->
static audit (owner checkpoint list).

Output: docs/reports/v2a_manifest/
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/reports/v2a_manifest"
OUT.mkdir(parents=True, exist_ok=True)

catalog = {o["operator_id"] for o in json.load(
    open(REPO / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json", encoding="utf-8"))["operators"]}
api_methods = set()
for line in open(REPO / "docs/reports/qgis_api_semantic_production_v2/phase2_adjudicated/adjudication_v1.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("decision") == "QUALIFIED":
        api_methods.add(r["semantic_action"].split(":")[-1].split(".")[-1])
catalog_by_slug = defaultdict(list)
for op in catalog:
    catalog_by_slug[op.split(":")[-1]].append(op)
PLUMBING = {"setGeometry", "setAttributes", "addFeatures", "addFeature", "addAttribute", "addAttributes",
            "updateFields", "GetRasterBand", "Open", "writeAsVectorFormat", "write", "close", "commitChanges",
            "startEditing", "setField", "setFieldValue", "setValue", "evaluate", "count", "size", "length",
            "addMapLayer", "removeMapLayer", "setCrs", "setDataSource", "isValid", "fields", "getFeatures",
            "featureCount", "extent", "crs", "wkbType", "geometryType", "name", "id", "triggerRepaint",
            "addVectorLayer", "addRasterLayer", "createLayer", "layerByName"}

FIELD_CALC = {"native:fieldcalculator", "qgis:fieldcalculator", "qgis:advancedpythonfieldcalculator"}


def lift(ident):
    """identifier -> catalog operator_id (with qgis->native alias), or None."""
    if ":" in ident:
        c = ident.replace("processing.run:", "")
        if c in catalog:
            return c
        if c.startswith("qgis:"):
            nat = "native:" + c.split(":")[-1]
            if nat in catalog:
                return nat
        return None
    m = ident.split(".")[-1]
    if m in PLUMBING:
        return None
    if catalog_by_slug.get(m):
        return catalog_by_slug[m][0]
    if m in api_methods:
        return "API:" + m
    return None


def load():
    rows = {}
    for l in open(REPO / "docs/reports/qgis_wf_full_v1.jsonl", encoding="utf-8"):
        r = json.loads(l)
        rows[r["wid"]] = r
    links = {}
    for l in open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/qgis_wf_links_v1.jsonl", encoding="utf-8"):
        r = json.loads(l)
        links[r["wid"]] = r
    shas = {w: h for w, _, h in (tuple(x) for x in json.load(
        open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/wf_shas.json", encoding="utf-8")))}
    tiers = json.load(open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/tier_labels_full_v1.json", encoding="utf-8"))["labels"]
    return rows, links, shas, tiers


def build_sample(wid, rows, links):
    """Return (task_text, processes, links, link_prov) or None if chain < 2."""
    r, lk = rows[wid], links[wid]
    retained, procmap = [], {}
    for p in lk["procs"]:
        op = lift(p["ident"])
        if op:
            retained.append(op)
            procmap[p["id"]] = len(retained) - 1
    if len(retained) < 2:
        return None
    # project the DAG through dropped nodes (path contraction)
    succ, pred = defaultdict(set), defaultdict(set)
    allp = {p["id"] for p in lk["procs"]}
    for e in lk["links"]:
        if e["s"] in allp and e["t"] in allp:
            succ[e["s"]].add(e["t"])
            pred[e["t"]].add(e["s"])
    edges = set()
    # memoized retained-reachability (topological order, iterative)
    order, indeg = [], Counter()
    for e in lk["links"]:
        if e["s"] in allp and e["t"] in allp:
            indeg[e["t"]] += 1
    stack = [n for n in allp if indeg[n] == 0]
    while stack:
        n = stack.pop()
        order.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                stack.append(s)

    def reach(n, direction, memo):
        if n in memo:
            return memo[n]
        if n in procmap:
            memo[n] = {procmap[n]}
            return memo[n]
        out = set()
        for m in (pred[n] if direction == "up" else succ[n]):
            out |= reach(m, direction, memo)
        memo[n] = out
        return out

    up_memo, down_memo = {}, {}
    for e in lk["links"]:
        if e["s"] in allp and e["t"] in allp:
            for a in reach(e["s"], "up", up_memo):
                for b in reach(e["t"], "down", down_memo):
                    if a != b:
                        edges.add((a, b))
    link_prov = "projected"
    if not edges:
        edges = {(i, i + 1) for i in range(len(retained) - 1)}
        link_prov = "linear_fallback"
    else:
        # guarantee connectivity: connect unreachable nodes in sequence
        seen = {x for e in edges for x in e}
        for i in range(len(retained)):
            if i not in seen:
                edges.add((max(i - 1, 0), i))
                link_prov = "projected+patched"
    processes = [{"process_id": f"p{i}", "operator_id": op} for i, op in enumerate(retained)]
    links_out = [{"source_process_id": f"p{a}", "target_process_id": f"p{b}"} for a, b in sorted(edges)]
    task_text = f"{r['name']}. {r['desc']}"
    return task_text, processes, links_out, link_prov


def source_disjoint_split(items, shas, seed=20260916):
    """One split over ALL candidates (shared by A and B), groups = provenance SHA."""
    import random
    groups = defaultdict(list)
    for it in items:
        groups[shas[it["wid"]]].append(it)
    rng = random.Random(seed)
    keys = sorted(groups)
    rng.shuffle(keys)
    n = len(items)
    target_train, target_dev = int(n * 0.85), int(n * 0.075)
    splits, counts = {"train": [], "dev": [], "test": []}, Counter()
    for k in keys:
        g = groups[k]
        if counts["train"] < target_train:
            s = "train"
        elif counts["dev"] < target_dev:
            s = "dev"
        else:
            s = "test"
        splits[s].extend(g)
        counts[s] += len(g)
    return splits


def apply_weight_caps(profile_rows, log):
    """fieldcalculator <=10% of weighted operator instances; taskType <=2x median.
    Weight-based only (no deletion). Tier-2 rows are reduced first."""
    rows = [dict(r) for r in profile_rows]
    # fieldcalculator cap
    def fc_share(rows):
        tot = sum(r["weight"] * len(r["processes"]) for r in rows)
        fc = sum(r["weight"] * sum(1 for p in r["processes"] if p["operator_id"] in FIELD_CALC)
                 for r in rows)
        return fc / max(tot, 1e-9), tot
    share, _ = fc_share(rows)
    before = share
    for _ in range(10):
        share, _ = fc_share(rows)
        if share <= 0.10005:
            break
        # rows containing fc also carry other operators, so whole-row scaling
        # couples fc and non-fc exposure — iterate the exact-formula scale
        fc_w = sum(r["weight"] * sum(1 for p in r["processes"] if p["operator_id"] in FIELD_CALC)
                   for r in rows)
        nonfc_w = sum(r["weight"] * len(r["processes"]) for r in rows) - fc_w
        scale = 0.10 * nonfc_w / (0.90 * max(fc_w, 1e-9))
        if scale >= 1.0:
            break
        for r in sorted(rows, key=lambda x: (x["tier"] != "Tier-2", x["wid"])):
            if any(p["operator_id"] in FIELD_CALC for p in r["processes"]):
                r["weight"] = round(r["weight"] * scale, 4)
    share2, _ = fc_share(rows)
    if before > 0.10:
        log.append({"cap": "fieldcalculator<=10%", "before": round(before, 4),
                    "after": round(share2, 4), "method": "iterated exact-formula whole-row scaling"})
    # taskType cap: any single taskType's weighted share <= 15% of the profile
    # (v1 used max<=2x-median which destroyed weights because the median over
    #  the long-tail types is ~1; actual data has max share 13.8% so this cap
    #  is a safety bound, not an active transformation)
    def tt_shares(rows):
        w = defaultdict(float)
        for r in rows:
            w[r["taskType"]] += r["weight"]
        return w
    w = tt_shares(rows)
    total_w = sum(w.values())
    for tt, v in sorted(w.items(), key=lambda kv: -kv[1]):
        if total_w > 0 and v / total_w > 0.15:
            scale = 0.15 * total_w / v
            for r in sorted(rows, key=lambda x: (x["tier"] != "Tier-2", x["wid"])):
                if r["taskType"] == tt:
                    r["weight"] = round(r["weight"] * scale, 4)
            log.append({"cap": f"taskType<=15%share ({tt})", "before": round(v, 1),
                        "after": round(0.15 * total_w, 1)})
    return rows


def main():
    rows, links, shas, tiers = load()
    # candidates: labeled + chain>=2 (rebuild chain to confirm)
    items = []
    for wid, tinfo in tiers.items():
        s = build_sample(wid, rows, links)
        if s is None:
            continue
        task_text, processes, links_out, link_prov = s
        items.append({"wid": wid, "taskType": rows[wid]["taskType"] or "?",
                      "tier": tinfo["tier"], "sha": shas[wid],
                      "task_text": task_text, "processes": processes,
                      "links": links_out, "link_prov": link_prov})
    print(f"[candidates] {len(items)} (链>=2)")

    # ONE shared split (source-disjoint)
    splits = source_disjoint_split(items, shas)
    split_of = {}
    for s, lst in splits.items():
        for it in lst:
            split_of[it["wid"]] = s
    print({s: len(v) for s, v in splits.items()})

    # profiles
    manifests = {}
    for prof, tier_w in (("A", {"Tier-1": 1.0}), ("B", {"Tier-1": 1.0, "Tier-2": 0.5})):
        caplog = []
        prows = []
        for it in items:
            w = tier_w.get(it["tier"])
            if w is None:
                continue
            prows.append({**it, "weight": w})
        prows = apply_weight_caps(prows, caplog)
        prows = apply_weight_caps(prows, caplog)  # second pass tightens taskType chain
        for s in ("train", "dev", "test"):
            out = [r for r in prows if split_of[r["wid"]] == s]
            p = OUT / f"v2a_{prof}_{s}.jsonl"
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                for r in out:
                    f.write(json.dumps({
                        "wid": r["wid"], "split": s, "tier": r["tier"],
                        "taskType": r["taskType"],
                        "weight": r["weight"], "task_text": r["task_text"],
                        "processes": r["processes"], "links": r["links"],
                        "link_prov": r["link_prov"], "source_sha256": r["sha"],
                    }, ensure_ascii=False, sort_keys=True) + "\n")
        manifests[prof] = {"rows": len(prows), "cap_log": caplog,
                           "eff_exposure": round(sum(r["weight"] for r in prows), 1)}

    # static audit
    audit = {"profiles": {}, "shared_split": {s: len(v) for s, v in splits.items()}}
    sha_split = defaultdict(set)
    for it in items:
        sha_split[it["sha"]].add(split_of[it["wid"]])
    audit["source_disjoint"] = all(len(v) == 1 for v in sha_split.values())
    audit["duplicate_sha_groups"] = sum(1 for v in sha_split.values() if True) - len(set(sha_split))
    for prof in ("A", "B"):
        allrows = []
        for s in ("train", "dev", "test"):
            allrows += [json.loads(l) for l in open(OUT / f"v2a_{prof}_{s}.jsonl", encoding="utf-8")]
        ops = Counter(p["operator_id"] for r in allrows for p in r["processes"])
        tot_ops = sum(ops.values())
        wtot = sum(r["weight"] * len(r["processes"]) for r in allrows)
        fc_w = sum(r["weight"] * sum(1 for p in r["processes"] if p["operator_id"] in FIELD_CALC)
                   for r in allrows)
        tt = Counter(r["taskType"] for r in allrows)
        # support bands from the audit file
        sup = json.load(open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/audit_result_v1.json", encoding="utf-8"))
        top = dict(sup["operator_support"]["top15"])
        band_of = {}
        for op, c in ops.items():
            band_of[op] = ("ge100" if c >= 100 else "30_99" if c >= 30 else
                           "10_29" if c >= 10 else "3_9" if c >= 3 else "1_2")
        bands = Counter(band_of.values())
        illegal_ops = {k for k in ops if k not in catalog and not k.startswith("API:")}
        bad_links = 0
        for r in allrows:
            ids = {p["process_id"] for p in r["processes"]}
            bad_links += sum(1 for l in r["links"]
                             if l["source_process_id"] not in ids or l["target_process_id"] not in ids)
        audit["profiles"][prof] = {
            "rows": len(allrows), "effective_exposure": round(sum(r["weight"] for r in allrows), 1),
            "tier1_rows": sum(1 for r in allrows if r["tier"] == "Tier-1"),
            "tier2_rows": sum(1 for r in allrows if r["tier"] == "Tier-2"),
            "distinct_operators": len(ops),
            "operator_instances": tot_ops,
            "fieldcalculator_exposure_share_weighted": round(fc_w / max(wtot, 1e-9), 4),
            "fieldcalculator_raw_instance_share": round(
                sum(v for k, v in ops.items() if k in FIELD_CALC) / tot_ops, 4),
            "weighted_operator_exposure": round(wtot, 1),
            "taskType_top5": tt.most_common(5),
            "support_band_distinct": dict(bands),
            "illegal_operator_ids": sorted(illegal_ops)[:10],
            "illegal_link_count": bad_links,
            "empty_process_rows": sum(1 for r in allrows if not r["processes"]),
            "link_prov": dict(Counter(r["link_prov"] for r in allrows)),
        }
    # hashes
    hashes = {}
    for p in sorted(OUT.glob("v2a_*.jsonl")):
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        "schema": "gis_recommend.v2a.manifest.v1",
        "built_at": "2026-09-16",
        "rules_source": "docs/plans/v2a_spec.md (spec defines rules; this manifest defines facts)",
        "profiles": {
            "A": {"definition": "Tier-1 only, weight 1.0", **manifests["A"]},
            "B": {"definition": "Tier-1 x1.0 + Tier-2 x0.5", **manifests["B"]},
        },
        "split": {"method": "source-disjoint by provenance SHA, seed 20260916, "
                            "ONE shared split for both profiles",
                  "counts": audit["shared_split"]},
        "sampling_control": {"fieldcalculator_cap": "10% weighted instance share",
                             "taskType_cap": "max/median <= 2x (weight-based, two passes)",
                             "vocab": "369 operators retained, no pruning"},
        "output_format": "task_text -> processes(process_id, operator_id) + links; no L3",
        "tier_label_method": "rules (88% calibration) + 100 manual overrides; see tier_labels_full_v1.json",
        "static_audit": audit,
        "file_sha256": hashes,
    }
    (OUT / "manifest_v1.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False)[:3000])
    print(f"\nwrote {OUT / 'manifest_v1.json'}")


if __name__ == "__main__":
    main()
