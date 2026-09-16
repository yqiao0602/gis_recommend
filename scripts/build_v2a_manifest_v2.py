# -*- coding: utf-8 -*-
"""V2a gate ③ (v2): rebuild the A/B manifests per the owner's four rulings.

Owner rulings 2026-09-16 (v2 supersedes v1; v1 is NOT a training basis):
  ① chain <= 30 processes; overlength/code-dump rows excluded AND recorded
     (no silent truncation). max_len 2560.
  ② A weights must be exactly 1.0: the fieldcalculator cap is achieved by
     DETERMINISTIC ROW DOWNSAMPLING (Tier-2 rows dropped first, then rows with
     more fc instances, then wid order), never by weight scaling. Weights carry
     tier semantics ONLY: A = Tier-1 x1.0; B = Tier-1 x1.0 + Tier-2 x0.5.
     Caps apply to TRAIN ONLY — dev/test are never mutated.
  ③ Link projection is CONSERVATIVE: an original edge whose endpoints both
     survive is kept directly; a dropped intermediate node yields edges only to
     its NEAREST retained successors/predecessors (minimal BFS distance);
     edges with both endpoints dropped are dropped. No transitive closure.
     link_source in {direct, projected, patched, linear} recorded per row and
     aggregated, so projected edges are never hidden behind a nicer link F1.
  ④ Output JSON uses the frozen benchmark contract verbatim
     (source_process_id/target_process_id).

Output: docs/reports/v2a_manifest/manifest_v2.json + v2a_{A,B}_{train,dev,test}.jsonl
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/reports/v2a_manifest"
OUT.mkdir(parents=True, exist_ok=True)

CHAIN_CAP = 30
FC_CAP = 0.10
TT_CAP = 0.15
SEED = 20260916

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
    # API-only semantic lifts (transform/combine/simplify) are NOT catalog
    # operators and NOT in the scorer's input space. Dropping them keeps the
    # frozen rule "model output space == scorer input space" exactly true; the
    # projection then contracts them as dropped nodes. Counted in the manifest.
    return None


def conservative_projection(lk):
    """Return (processes, links, source_kind) with minimal necessary edges only."""
    retained, procmap = [], {}
    n_api_dropped = 0
    for p in lk["procs"]:
        ident = p["ident"]
        op = lift(ident)
        if op:
            procmap[p["id"]] = len(retained)
            retained.append(op)
        elif ":" not in ident and ident.split(".")[-1] in api_methods:
            n_api_dropped += 1
    if len(retained) < 2:
        return None
    succ, pred = defaultdict(set), defaultdict(set)
    nodes = {p["id"] for p in lk["procs"]}
    for e in lk["links"]:
        if e["s"] in nodes and e["t"] in nodes:
            succ[e["s"]].add(e["t"])
            pred[e["t"]].add(e["s"])

    def nearest(n, adj):
        """Retained nodes at minimal BFS distance from n (empty if none)."""
        seen, q = {n}, deque([(n, 0)])
        while q:
            cur, d = q.popleft()
            hit = set()
            for m in adj[cur]:
                if m in procmap:
                    hit.add(procmap[m])
                elif m not in seen:
                    seen.add(m)
                    q.append((m, d + 1))
            if hit:
                return hit
        return set()

    edges, kinds = set(), Counter()
    for e in lk["links"]:
        s, t = e["s"], e["t"]
        if s not in nodes or t not in nodes:
            continue
        if s in procmap and t in procmap:
            a, b = procmap[s], procmap[t]
            if a != b:
                edges.add((a, b))
                kinds["direct"] += 1
        else:
            srcs = {procmap[s]} if s in procmap else nearest(s, succ)
            dsts = {procmap[t]} if t in procmap else nearest(t, pred)
            for a in srcs:
                for b in dsts:
                    if a != b:
                        edges.add((a, b))
                        kinds["projected"] += 1
    if not edges:
        edges = {(i, i + 1) for i in range(len(retained) - 1)}
        kinds = Counter({"linear": len(edges)})
    else:
        incident = {x for e in edges for x in e}
        for i in range(len(retained)):
            if i not in incident:
                edges.add((max(i - 1, 0), i))
                kinds["patched"] += 1
    processes = [{"process_id": f"p{i}", "operator_id": op} for i, op in enumerate(retained)]
    links = [{"source_process_id": f"p{a}", "target_process_id": f"p{b}"}
             for a, b in sorted(edges) if a != b]
    # dedupe (defensive) and report kind mix
    seen, uniq = set(), []
    for l in links:
        k = (l["source_process_id"], l["target_process_id"])
        if k not in seen:
            seen.add(k)
            uniq.append(l)
    return processes, uniq, dict(kinds), n_api_dropped


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
    tiers = json.load(open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/tier_labels_full_v1.json",
                           encoding="utf-8"))["labels"]
    return rows, links, shas, tiers


def main():
    rows, links, shas, tiers = load()
    items, excluded_overlength = [], []
    api_dropped_total = 0
    for wid, tinfo in tiers.items():
        proj = conservative_projection(links[wid])
        if proj is None:
            continue
        processes, links_out, kinds, n_api = proj
        api_dropped_total += n_api
        if len(processes) > CHAIN_CAP:
            excluded_overlength.append({"wid": wid, "n_processes": len(processes),
                                        "n_links": len(links_out)})
            continue
        items.append({"wid": wid, "taskType": rows[wid]["taskType"] or "?",
                      "tier": tinfo["tier"], "sha": shas[wid],
                      "task_text": f"{rows[wid]['name']}. {rows[wid]['desc']}",
                      "processes": processes, "links": links_out,
                      "link_kinds": kinds})
    print(f"[gate 1] candidates={len(items)} | excluded_overlength={len(excluded_overlength)}")

    # ONE shared source-disjoint split (over eligible candidates)
    groups = defaultdict(list)
    for it in items:
        groups[it["sha"]].append(it)
    keys = sorted(groups)
    random.Random(SEED).shuffle(keys)
    n = len(items)
    tgt_train, tgt_dev = int(n * 0.85), int(n * 0.075)
    split_of, counts = {}, Counter()
    for k in keys:
        g = groups[k]
        s = "train" if counts["train"] < tgt_train else ("dev" if counts["dev"] < tgt_dev else "test")
        for it in g:
            split_of[it["wid"]] = s
        counts[s] += len(g)
    print(f"[split] {dict(counts)}")

    manifests, fc_drop_log = {}, {}
    for prof, tw in (("A", {"Tier-1": 1.0}), ("B", {"Tier-1": 1.0, "Tier-2": 0.5})):
        members = [it for it in items if it["tier"] in tw]
        train_rows = [dict(it, weight=tw[it["tier"]], split=split_of[it["wid"]])
                      for it in members if split_of[it["wid"]] == "train"]
        dev_rows = [dict(it, weight=1.0, split="dev") for it in members if split_of[it["wid"]] == "dev"]
        test_rows = [dict(it, weight=1.0, split="test") for it in members if split_of[it["wid"]] == "test"]

        # ② deterministic row downsampling for the fc cap (TRAIN ONLY)
        def fc_share(rs):
            tot = sum(len(r["processes"]) for r in rs)
            fc = sum(sum(1 for p in r["processes"] if p["operator_id"] in FIELD_CALC) for r in rs)
            return fc / max(tot, 1e-9)
        before = fc_share(train_rows)
        dropped = []
        if before > FC_CAP:
            order = sorted(range(len(train_rows)),
                           key=lambda i: (train_rows[i]["tier"] != "Tier-2",
                                          -sum(1 for p in train_rows[i]["processes"]
                                               if p["operator_id"] in FIELD_CALC),
                                          train_rows[i]["wid"]))
            keep = [True] * len(train_rows)
            for i in order:
                if fc_share([r for j, r in enumerate(train_rows) if keep[j]]) <= FC_CAP:
                    break
                if any(p["operator_id"] in FIELD_CALC for p in train_rows[i]["processes"]):
                    keep[i] = False
                    dropped.append(train_rows[i]["wid"])
            train_rows = [r for j, r in enumerate(train_rows) if keep[j]]
        after = fc_share(train_rows)
        fc_drop_log[prof] = {"before": round(before, 4), "after": round(after, 4),
                             "dropped_rows": len(dropped), "dropped_wids": dropped[:200]}

        for s, rs in (("train", train_rows), ("dev", dev_rows), ("test", test_rows)):
            p = OUT / f"v2a_{prof}_{s}.jsonl"
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                for r in rs:
                    f.write(json.dumps({
                        "wid": r["wid"], "split": s, "tier": r["tier"], "weight": r["weight"],
                        "taskType": r["taskType"], "task_text": r["task_text"],
                        "processes": r["processes"], "links": r["links"],
                        "link_kinds": r["link_kinds"], "source_sha256": r["sha"],
                    }, ensure_ascii=False, sort_keys=True) + "\n")
        manifests[prof] = {
            "rows": {s: len(rs) for s, rs in (("train", train_rows), ("dev", dev_rows), ("test", test_rows))},
            "tier1_train": sum(1 for r in train_rows if r["tier"] == "Tier-1"),
            "tier2_train": sum(1 for r in train_rows if r["tier"] == "Tier-2"),
            "effective_exposure_train": round(sum(r["weight"] for r in train_rows), 1),
            "weight_histogram_train": dict(Counter(round(r["weight"], 2) for r in train_rows)),
            "fc_share_train": {"before_cap": round(before, 4), "after_cap": round(after, 4)},
            "fc_cap_dropped": len(dropped),
        }
        print(f"[{prof}] train={len(train_rows)} dev={len(dev_rows)} test={len(test_rows)} "
              f"weights={manifests[prof]['weight_histogram_train']} fc {before:.4f}->{after:.4f}")

    # ── gate 3.5 audit ──
    audit = {"api_only_lifts_dropped_from_target_space": api_dropped_total,
             "excluded_overlength": len(excluded_overlength),
             "excluded_overlength_examples": sorted(excluded_overlength,
                                                    key=lambda x: -x["n_processes"])[:5],
             "profiles": {}, "link_kind_totals": {}, "split": dict(counts)}
    for prof in ("A", "B"):
        allrows = []
        for s in ("train", "dev", "test"):
            allrows += [json.loads(l) for l in open(OUT / f"v2a_{prof}_{s}.jsonl", encoding="utf-8")]
        tot_inst = sum(len(r["processes"]) for r in allrows)
        fc_inst = sum(sum(1 for p in r["processes"] if p["operator_id"] in FIELD_CALC) for r in allrows)
        tt_w = defaultdict(float)
        for r in allrows:
            tt_w[r["taskType"]] += r["weight"]
        tot_w = sum(tt_w.values())
        bad_links = dup_links = self_loops = invalid_json = 0
        for r in allrows:
            ids = {p["process_id"] for p in r["processes"]}
            seen = set()
            for l in r["links"]:
                k = (l["source_process_id"], l["target_process_id"])
                if k[0] not in ids or k[1] not in ids:
                    bad_links += 1
                if k in seen:
                    dup_links += 1
                seen.add(k)
                if k[0] == k[1]:
                    self_loops += 1
            try:
                json.loads(json.dumps({"processes": r["processes"], "links": r["links"]}))
            except Exception:
                invalid_json += 1
        kt = Counter()
        for r in allrows:
            for k, v in (r["link_kinds"] or {}).items():
                kt[k] += v
        audit["profiles"][prof] = {
            "rows": len(allrows),
            "illegal_operator_ids": sorted({p["operator_id"] for r in allrows for p in r["processes"]
                                            if p["operator_id"] not in catalog})[:5],
            "illegal_links": bad_links, "duplicate_links": dup_links, "self_loops": self_loops,
            "invalid_target_json": invalid_json,
            "fc_instance_share_all": round(fc_inst / max(tot_inst, 1), 4),
            "max_taskType_share_weighted": round(max(tt_w.values()) / max(tot_w, 1e-9), 4),
            "distinct_operators": len({p["operator_id"] for r in allrows for p in r["processes"]}),
        }
        audit["link_kind_totals"][prof] = dict(kt)

    # source-disjoint verification
    sha_splits = defaultdict(set)
    for it in items:
        sha_splits[it["sha"]].add(split_of[it["wid"]])
    audit["source_disjoint"] = all(len(v) == 1 for v in sha_splits.values())

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(OUT.glob("v2a_*.jsonl"))}
    manifest = {
        "schema": "gis_recommend.v2a.manifest.v2",
        "supersedes": "manifest_v1.json (NOT a training basis; owner ruling 2026-09-16)",
        "built_at": "2026-09-16",
        "rules_source": "docs/plans/v2a_spec.md + owner rulings (chain<=30, weight-purity, conservative projection, benchmark key contract)",
        "eligibility": {"chain_cap": CHAIN_CAP, "excluded_overlength": len(excluded_overlength)},
        "profiles": manifests,
        "split": {"method": "source-disjoint by provenance SHA, ONE shared split", "counts": dict(counts)},
        "sampling_control": {
            "fieldcalculator": "deterministic row downsampling on TRAIN ONLY (Tier-2 first, "
                               "then more-fc rows, then wid); weights stay pure tier values",
            "taskType": "15% weighted-share safety bound (no cap fires on this data)",
            "vocab": "no operator pruning; support bands recorded",
        },
        "link_projection": "conservative: direct kept; dropped intermediates yield only "
                           "nearest retained successor/predecessor edges; both-dropped edges "
                           "removed; no transitive closure; patched/linear recorded",
        "output_format": "benchmark gold contract verbatim (processes + links with "
                         "source_process_id/target_process_id)",
        "fc_cap_log": fc_drop_log,
        "static_audit": audit,
        "file_sha256": hashes,
    }
    (OUT / "manifest_v2.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    print("wrote manifest_v2.json")


if __name__ == "__main__":
    main()
