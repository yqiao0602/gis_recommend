#!/usr/bin/env python3
"""Build a bounded, read-only GEE Semantic Planner schema pilot.

Pilot outputs are provisional review evidence only.
The source JSONL is never modified; no model is loaded, trained, or run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

PILOT_SCHEMA = "gee_semantic_planner_v1_pilot"
MAX_ROWS = 40
TARGET_PER_STRATUM = 5
RESERVOIR_PER_STRATUM = 50
STRATA = (
    "ordinary_remote_sensing", "index_concept", "temporal_series",
    "classification_regression", "multi_source", "branch_or_parallel",
    "repetition_or_run_cap", "long_or_multi_output",
)
PATTERNS = {
    "remote": r"\b(?:imagery|image|raster|remote sensing|surface reflectance|land cover|land surface)\b",
    "index": r"\b(?:ndvi|ndwi|ndbi|evi|savi|mndwi|ndmi|lai)\b",
    "sensor": r"\b(?:sentinel[- ]?[123]|landsat(?:[- ]?[45789])?|modis|prism|dynamic world)\b",
    "temporal": r"\b(?:monthly|month|annual(?:ly)?|yearly|season(?:al)?|time[- ]series|between\s+\d{4}|\d{4}[-/]\d{2}[-/]\d{2})\b",
    "classification": r"\b(?:classif(?:y|ication|ied)|land cover|classes|mosaic|mode composite)\b",
    "regression": r"\b(?:regression|regressed|residuals?|rmse|mae|pearson|correlation)\b",
    "multi_source": r"\b(?:combine|combining|multiple datasets?|two datasets?|against|with .* data|pre[- ]and post)\b",
    "branch": r"\b(?:separately|separate|two outputs?|multiple outputs?|parallel|branch|ascending and descending|asc(?:ending)? and desc(?:ending)?)\b",
    "output": r"\b(?:export|exports|csv|chart|scatter|map|visuali[sz]|output|outputs|generate .* files?)\b",
    "statistics": r"\b(?:mean|median|max(?:imum)?|minimum|min(?:imum)?|mode|sum|average|standard deviation|percentile)\b",
    "spatial": r"\b(?:region|area|polygon|roi|state|country|basin|watershed|boundary|clipped?|study area)\b",
    "threshold": r"\b(?:threshold|below|above|greater than|less than|detect|identify burned|mask(?:ed|ing)?)\b",
}
RX = {key: re.compile(value, re.I) for key, value in PATTERNS.items()}
FORBIDDEN = {
    "gee_api": re.compile(r"\bee\.[A-Za-z_]"),
    "qgis_provider_id": re.compile(r"\b(?:native|gdal|grass7?|saga|otb|qgis)\s*:", re.I),
    "qgis_parameter_key": re.compile(r"\b(?:INPUT|OVERLAY|DISTANCE|SEGMENTS|DISSOLVE|PIXEL_SIZE)\b"),
    "asset_id": re.compile(r"\b(?:COPERNICUS|LANDSAT|MODIS)/[A-Za-z0-9_./-]+|\busers/[A-Za-z0-9_./-]+", re.I),
    "band_id": re.compile(r"\bB(?:[0-9]{1,3}|QA[0-9]*)\b", re.I),
    "source_path": re.compile(r"(?:[A-Za-z]:\\|/home/|/mnt/|/tmp/)[^\s]+", re.I),
    "code_fragment": re.compile(r"\b(?:function\s*\(|return\s+|def\s+|=>|\.map\s*\()", re.I),
}


def iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_no}: row is not an object")
                yield line_no, row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def task_text(row: dict[str, Any]) -> str:
    return str(row.get("instruction", ""))


def family_tokens(row: dict[str, Any]) -> list[str]:
    return [x.strip() for x in str(row.get("semantic_chain_raw", "")).split("->") if x.strip()]


def has(row: dict[str, Any], key: str) -> bool:
    return bool(RX[key].search(task_text(row)))


def strata_for(row: dict[str, Any]) -> set[str]:
    families = family_tokens(row)
    raw_len = int(row.get("original_semantic_length") or len(families))
    final_len = int(row.get("final_semantic_length") or len(families))
    load_count = sum(f in {"RASTER_LOAD", "VECTOR_LOAD"} for f in families)
    tags: set[str] = set()
    if has(row, "index"): tags.add("index_concept")
    if has(row, "temporal"): tags.add("temporal_series")
    if has(row, "classification") or has(row, "regression"): tags.add("classification_regression")
    if load_count >= 2 or has(row, "multi_source"): tags.add("multi_source")
    if load_count >= 3 or has(row, "branch"): tags.add("branch_or_parallel")
    if bool(row.get("run_cap_applied")) or any(a == b for a, b in zip(families, families[1:])) or raw_len > max(1, final_len) * 1.4:
        tags.add("repetition_or_run_cap")
    if raw_len >= 50 or len(task_text(row)) >= 1400 or len(RX["output"].findall(task_text(row))) >= 2:
        tags.add("long_or_multi_output")
    if has(row, "remote") or has(row, "sensor"): tags.add("ordinary_remote_sensing")
    return tags


def evidence(value: Any, status: str, task=(), implementation=()) -> dict[str, Any]:
    if status not in {"supported", "inferred", "unknown", "blocked"}:
        raise ValueError(f"invalid evidence status: {status}")
    return {"value": value, "status": status, "evidence": {"task": list(task), "implementation": list(implementation)}}


def cue(row: dict[str, Any], key: str) -> str | None:
    match = RX[key].search(task_text(row))
    return match.group(0) if match else None


def temporal_scope(task: str) -> str | None:
    if re.search(r"\bmonthly\b|\bmonth\b", task, re.I): return "monthly"
    if re.search(r"\bannual(?:ly)?\b|\byearly\b", task, re.I): return "annual"
    if re.search(r"\bseason(?:al)?\b", task, re.I): return "seasonal"
    if re.search(r"\btime[- ]series\b", task, re.I): return "time_series"
    return None


def validate_links(planner_view: dict[str, Any]) -> None:
    stages = planner_view["workflow"]["stages"]
    seqs = {stage["seq"] for stage in stages}
    seen = set()
    for link in planner_view["workflow"]["links"]:
        source, target, relation = link.get("source"), link.get("target"), link.get("relation")
        if source not in seqs or target not in seqs: raise ValueError("dangling link endpoint")
        if source == target: raise ValueError("self link")
        key = (source, target, relation)
        if key in seen: raise ValueError("duplicate link")
        seen.add(key)


def reservoir_add(reservoir, item, seen_count, capacity, rng):
    """Deterministic Algorithm-R update; returns updated stratum count."""
    seen_count += 1
    if len(reservoir) < capacity:
        reservoir.append(item)
        return seen_count
    index = rng.randrange(seen_count)
    if index < capacity:
        reservoir[index] = item
    return seen_count


def build_bounded_reservoirs_from_rows(rows, seed: int):
    """Test helper using the same streaming identity checks as file input."""
    rng = random.Random(seed)
    reservoirs = {stratum: [] for stratum in STRATA}
    seen_counts = Counter()
    seen_scripts = set()
    for line_no, row in rows:
        script = row.get("script")
        if not script:
            raise ValueError(f"missing source_script at line {line_no}")
        script = str(script)
        if script in seen_scripts:
            raise ValueError(f"duplicate source_script: {script}")
        seen_scripts.add(script)
        tags = strata_for(row)
        for stratum in sorted(tags):
            seen_counts[stratum] = reservoir_add(reservoirs[stratum], (line_no, row, tags), seen_counts[stratum], RESERVOIR_PER_STRATUM, rng)
    return reservoirs, dict(seen_counts), len(rows)


def build_bounded_reservoirs(source: Path, seed: int):
    """Stream source rows and retain only bounded per-stratum reservoirs."""
    rng = random.Random(seed)
    reservoirs = {stratum: [] for stratum in STRATA}
    seen_counts = Counter()
    rows_scanned = 0
    source_scripts = set()
    for line_no, row in iter_jsonl(source):
        rows_scanned += 1
        script = row.get("script")
        if not script:
            raise ValueError(f"missing source_script at line {line_no}")
        script = str(script)
        if script in source_scripts:
            raise ValueError(f"duplicate source_script: {script}")
        source_scripts.add(script)
        tags = strata_for(row)
        for stratum in sorted(tags):
            seen_counts[stratum] = reservoir_add(
                reservoirs[stratum], (line_no, row, tags),
                seen_counts[stratum], RESERVOIR_PER_STRATUM, rng)
    return reservoirs, dict(seen_counts), rows_scanned


def select_from_reservoirs(reservoirs, existing, max_rows=MAX_ROWS):
    pool = {}
    for stratum in STRATA:
        for line_no, row, tags in reservoirs[stratum]:
            script = str(row["script"])
            pool.setdefault(script, (line_no, row, tags))
    selected, used, coverage = [], set(), Counter()
    selected_task_keys = set()
    stop_reason = "max_rows_reached"
    while len(selected) < max_rows:
        best = None
        for script, (line_no, row, tags) in pool.items():
            if script in used:
                continue
            deficits = [s for s in sorted(tags) if coverage[s] < TARGET_PER_STRATUM]
            task_key = re.sub(r"\s+", " ", task_text(row).strip().lower())
            score = (len(deficits), int(task_key not in selected_task_keys), int(script in existing), -line_no)
            if best is None or score > best[0]:
                best = (score, script, line_no, row, tags, deficits, task_key)
        if best is None:
            stop_reason = "candidate_pool_exhausted"
            break
        _, script, line_no, row, tags, deficits, task_key = best
        primary = sorted(deficits)[0] if deficits else (sorted(tags)[0] if tags else "unclassified")
        selected.append({
            "source_line_no": line_no, "source_script": script,
            "strata": sorted(tags), "primary_strata": primary,
            "secondary_strata": sorted(set(tags) - {primary}),
            "selection_reason": "maximal marginal gain from deterministic per-stratum Algorithm-R reservoirs" if deficits else "independent diversity fill after stratum targets",
            "marginal_gain": len(deficits), "covered_deficits": deficits,
            "task_key": task_key,
        })
        used.add(script)
        selected_task_keys.add(task_key)
        for stratum in deficits:
            coverage[stratum] += 1
    return selected, {s: coverage[s] for s in STRATA}, pool, stop_reason


def build_candidate(row: dict[str, Any], source_line_no: int, source_sha256: str, tags: set[str]) -> dict[str, Any]:
    task = task_text(row)
    stages: list[dict[str, Any]] = []
    field_evidence: dict[str, Any] = {}

    def add_stage(operation: str, purpose: str, obj: str | None, attrs: dict[str, Any], cue_text: str) -> None:
        seq = len(stages) + 1
        stage = {
            "seq": seq,
            "operation": evidence(operation, "inferred", [cue_text]),
            "purpose": evidence(purpose, "inferred", [cue_text]),
            "object": evidence(obj, "inferred" if obj else "unknown", [cue_text]),
            "attributes": evidence(attrs, "inferred" if attrs else "unknown", [cue_text]),
        }
        stages.append(stage)
        for name in ("operation", "purpose", "object", "attributes"):
            field_evidence[f"workflow.stages[{seq}].{name}"] = stage[name]

    sensor, index, statistic = cue(row, "sensor"), cue(row, "index"), cue(row, "statistics")
    if sensor or re.search(r"\b(?:imagery|image|raster|dataset|data)\b", task, re.I):
        add_stage("DATA_ACQUISITION", "obtain imagery or analysis data", "remote_sensing_imagery" if sensor else None, {"sensor": sensor} if sensor else {}, "task imagery/sensor cue")
    if has(row, "spatial"):
        add_stage("SPATIAL_SELECTION", "restrict analysis to geographic scope", "analysis_region", {}, "task spatial cue")
    if has(row, "temporal"):
        scope = temporal_scope(task)
        add_stage("TEMPORAL_SELECTION", "select observation period or temporal units", "time_series", {"temporal_scope": scope} if scope else {}, "task temporal cue")
    if index:
        add_stage("INDEX_COMPUTATION", "derive requested spectral/environmental index", "derived_index", {"index": index.upper()}, "task index cue")
    if has(row, "classification"):
        add_stage("CLASSIFICATION", "assign or analyze thematic classes", "classified_surface", {}, "task classification cue")
    elif has(row, "regression"):
        add_stage("REGRESSION_OR_VALIDATION", "estimate or validate a continuous relationship", "continuous_measure", {}, "task regression cue")
    if has(row, "threshold"):
        add_stage("THRESHOLD_OR_MASK", "apply a task-relevant threshold or mask", "analysis_measure", {}, "task threshold cue")
    if statistic:
        add_stage("AGGREGATION", "summarize observations using stated statistic", "summary_measure", {"statistic": statistic.lower()}, "task statistic cue")
    if not stages:
        stages.append({"seq": 1, "operation": evidence(None, "unknown"), "purpose": evidence(None, "unknown"), "object": evidence(None, "unknown"), "attributes": evidence({}, "unknown")})

    links = [{"source": a["seq"], "target": b["seq"], "relation": "ordered_before", "status": "inferred", "evidence": {"task": ["candidate stage order"], "implementation": []}} for a, b in zip(stages, stages[1:])]
    unresolved = []
    if "branch_or_parallel" in tags or "multi_source" in tags:
        unresolved.append({"relation": "dependency", "status": "unresolved", "reason": "multiple inputs/outputs apparent", "evidence": {"task": ["multiple inputs/outputs apparent"], "implementation": []}})
    if re.search(r"\b(?:for each year|per year|each year|separately for each year)\b", task, re.I):
        repeat = evidence("per_year", "inferred", ["explicit per-year task cue"])
    elif re.search(r"\b(?:for each class|per class|each class|each category)\b", task, re.I):
        repeat = evidence("per_class", "inferred", ["explicit per-class task cue"])
    else:
        repeat = evidence(None, "unknown")

    outputs: list[dict[str, Any]] = []
    def output(obj: str, purpose: str, cue_text: str) -> dict[str, Any]:
        return {"object": evidence(obj, "inferred", [cue_text]), "purpose": evidence(purpose, "inferred", [cue_text]), "attributes": evidence({}, "unknown")}
    if has(row, "output"):
        if re.search(r"\b(?:chart|scatter)\b", task, re.I): outputs.append(output("chart_or_diagnostic_plot", "visualize analysis results", "task chart cue"))
        if re.search(r"\b(?:csv|table|files?)\b", task, re.I): outputs.append(output("tabular_result", "export analysis results", "task export cue"))
        if not outputs: outputs.append(output("analysis_result", "produce requested GIS result", "task output cue"))

    planner_visible = {"workflow": {"stages": stages, "links": links, "unresolved_dependencies": unresolved, "repeat_semantics": repeat}, "outputs": outputs}
    validate_links(planner_visible)
    leak_input = {"workflow": planner_visible["workflow"], "outputs": planner_visible["outputs"]}
    leakage_hits = [name for name, pattern in FORBIDDEN.items() if pattern.search(json.dumps(leak_input, ensure_ascii=False, sort_keys=True))]
    sample_id = f"g0-line-{source_line_no}"
    canonical = str(row.get("gee_canonical_chain", ""))
    provenance = {
        "source_line_no": source_line_no, "source_script": row.get("script"), "source_sha256": source_sha256,
        "pilot_sample_id": sample_id, "split": row.get("split"), "task_type": row.get("task_type"),
        "semantic_chain_raw": row.get("semantic_chain_raw"), "semantic_chain_rle": row.get("semantic_chain_rle"),
        "run_cap_applied": row.get("run_cap_applied"), "original_semantic_length": row.get("original_semantic_length"),
        "final_semantic_length": row.get("final_semantic_length"), "gee_canonical_chain": row.get("gee_canonical_chain"),
        "author_proxy": row.get("author_proxy"), "implementation_iteration_evidence": evidence("map_present" if ".map" in canonical else None, "supported" if ".map" in canonical else "unknown", implementation=["canonical chain contains map-like iteration"] if ".map" in canonical else []),
    }
    return {"pilot_only": True, "training_admission": "not_granted", "production_samples": 0, "semantic_gold": False, "schema_status": "pilot_only", "provenance": provenance, "strata": sorted(tags), "planner_view": {"schema": PILOT_SCHEMA, "sample_id": sample_id, "task": task, **planner_visible, "review": {"status": "blocked" if leakage_hits else "pending", "field_evidence": field_evidence, "leakage_hits": leakage_hits, "uncertainty": ["candidate fields require human review"]}}}


def load_existing(path: Path | None) -> set[str]:
    if not path or not path.is_file():
        return set()

    existing: set[str] = set()

    for _, row in iter_jsonl(path):
        script = row.get("source_script") or row.get("script")
        if script:
            existing.add(str(script))

    return existing


NORMALIZATION_PATTERNS = {
    "index": r"\b(?:ndvi|ndwi|ndbi|evi|savi|mndwi|ndmi|lai)\b",
    "sensor": r"\b(?:sentinel[- ]?[123]|landsat(?:[- ]?[45789])?|modis|prism|dynamic world)\b",
    "temporal_scope": r"\b(?:monthly|month|annual|yearly|season(?:al)?|time[- ]series)\b",
    "repeat_scope": r"\b(?:for each year|per year|each year|for each class|per class|each class)\b",
    "statistic": r"\b(?:mean|median|average|max(?:imum)?|minimum|min(?:imum)?|mode|sum)\b",
    "task_objective": r"\b(?:classification|classify|regression|regressed)\b",
}


def normalized_task(task: str, contrast: str) -> set[str]:
    pattern = NORMALIZATION_PATTERNS[contrast]
    normalized = re.sub(pattern, " <contrast> ", task.lower())
    return set(re.findall(r"[a-z0-9]+", normalized))


def jaccard(a, b): return len(a & b) / len(a | b) if a | b else 0.0


def discover_counterfactuals(records):
    contrasts = {
        "index": (r"\bndvi\b", r"\bndwi\b|\bndbi\b|\bevi\b", "workflow.stages[].attributes.index"),
        "sensor": (r"\bsentinel", r"\blandsat", "workflow.stages[].attributes.sensor"),
        "temporal_scope": (r"\bmonthly\b|\bmonth", r"\bannual\b|\byearly\b", "workflow.stages[].attributes.temporal_scope"),
        "repeat_scope": (r"\bper year\b|\bfor each year\b", r"\bper class\b|\bfor each class\b", "workflow.repeat_semantics"),
        "statistic": (r"\bmean\b|\baverage\b", r"\bmedian\b", "workflow.stages[].attributes.statistic"),
        "task_objective": (r"\bclassification\b|\bclassify\b", r"\bregression\b|\bregressed\b", "workflow.stages[].operation"),
    }

    def sample_id(record):
        return record["planner_view"]["sample_id"]

    def task_key(record):
        return re.sub(r"\s+", " ", record["planner_view"]["task"].strip().lower())

    def line_no(record):
        return int(record["provenance"]["source_line_no"])

    results = []
    for name, (left_re, right_re, slot) in contrasts.items():
        left_only, right_only, ambiguous = [], [], []
        left_rx, right_rx = re.compile(left_re, re.I), re.compile(right_re, re.I)
        for record in records:
            task = record["planner_view"]["task"]
            left_hit, right_hit = bool(left_rx.search(task)), bool(right_rx.search(task))
            if left_hit and right_hit:
                ambiguous.append(record)
            elif left_hit:
                left_only.append(record)
            elif right_hit:
                right_only.append(record)

        candidates = []
        for a in left_only:
            for b in right_only:
                if sample_id(a) == sample_id(b) or task_key(a) == task_key(b):
                    continue
                similarity = jaccard(
                    normalized_task(a["planner_view"]["task"], name),
                    normalized_task(b["planner_view"]["task"], name),
                )
                if similarity >= 0.35:
                    candidates.append((similarity, a, b))

        common = {
            "contrast": name,
            "candidate_schema_slot": slot,
            "ambiguous_sample_ids": [sample_id(r) for r in ambiguous],
            "ambiguous_sample_count": len(ambiguous),
        }
        if not candidates:
            results.append({
                **common,
                "status": "ambiguous" if ambiguous and not (left_only and right_only) else "undetermined" if left_only and right_only else "unavailable",
                "reason": "no eligible distinct-task pair passed similarity checks; ambiguous tasks excluded",
            })
            continue

        similarity, a, b = max(
            candidates,
            key=lambda x: (x[0], -line_no(x[1]), -line_no(x[2])),
        )
        assert sample_id(a) != sample_id(b)
        assert task_key(a) != task_key(b)
        results.append({
            **common,
            "status": "undetermined",
            "candidate": True,
            "pair_id": f"{name}:{sample_id(a)}:{sample_id(b)}",
            "left_sample_id": sample_id(a),
            "right_sample_id": sample_id(b),
            "same_task": False,
            "same_intent": "pending_human_review",
            "ambiguous_concept_match": False,
            "shared_context": round(similarity, 4),
            "expected_semantic_difference": name,
            "evidence": {
                "task": [a["planner_view"]["task"], b["planner_view"]["task"]],
                "source": [
                    {"sample_id": sample_id(a), "source_script": a["provenance"]["source_script"], "source_line_no": line_no(a), "source_sha256": a["provenance"]["source_sha256"]},
                    {"sample_id": sample_id(b), "source_script": b["provenance"]["source_script"], "source_line_no": line_no(b), "source_sha256": b["provenance"]["source_sha256"]},
                ],
            },
        })
    return results


def project_without(record, field_name):
    view = json.loads(json.dumps(record["planner_view"], ensure_ascii=False)); workflow = view["workflow"]
    if field_name.startswith("attributes."):
        key = field_name.split(".", 1)[1]
        for stage in workflow["stages"]: stage.get("attributes", {}).get("value", {}).pop(key, None)
    elif field_name in {"operation", "purpose", "object"}:
        for stage in workflow["stages"]: stage[field_name] = {"value": None, "status": "unknown"}
    elif field_name == "links": workflow["links"] = []
    elif field_name == "outputs": view["outputs"] = []
    elif field_name == "repeat_scope": workflow["repeat_semantics"] = {"value": None, "status": "unknown"}
    return view


def omission_audit(records, pairs):
    fields = ("operation", "purpose", "object", "attributes.index", "attributes.sensor", "attributes.temporal_scope", "attributes.statistic", "attributes.class_set", "attributes.threshold_role", "outputs", "links", "repeat_scope")
    by_id = {r["planner_view"]["sample_id"]: r for r in records}; available = [p for p in pairs if p.get("status") == "available"]; results = []
    for field in fields:
        tested = [p for p in available if p.get("candidate_schema_slot", "").endswith(field)]
        if not tested:
            results.append({"field": field, "status": "insufficient_pair_evidence", "reason": "no human-approved available pair for this slot", "cases": []}); continue
        cases = [{"pair": p["pair_id"], "status": "high-impact_collision"} for p in tested if project_without(by_id[p["left_sample_id"]], field) == project_without(by_id[p["right_sample_id"]], field)]
        results.append({"field": field, "status": "high-impact_collision" if cases else "undetermined", "cases": cases})
    return results


def invariance_discovery(records):
    groups = defaultdict(list)
    for record in records:
        tokens = set(re.findall(r"[a-z0-9]+", record["planner_view"]["task"].lower())); signature = tuple(sorted(tokens - {"sentinel", "landsat", "ndvi", "ndwi", "ndbi", "evi"}))
        if signature: groups[signature].append(record)
    results = []
    for signature, group in groups.items():
        chains = {str(r["provenance"]["gee_canonical_chain"] or "") for r in group}
        if len(group) >= 2 and len(chains) >= 2: results.append({"status": "undetermined", "reason": "candidate group requires human intent review", "task_signature": signature, "sample_ids": [r["planner_view"]["sample_id"] for r in group], "implementation_variants": len(chains)})
    return results or [{"status": "unavailable", "reason": "no defensible equivalent-implementation candidate group"}]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--source", type=Path, required=True); parser.add_argument("--existing-sample", type=Path); parser.add_argument("--out-dir", type=Path, required=True); args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_sha = sha256_file(args.source)
    reservoir_seed = 20261008
    reservoirs, reservoir_seen_counts, rows_scanned = build_bounded_reservoirs(args.source, reservoir_seed)
    selected, coverage, pool, selection_stop_reason = select_from_reservoirs(reservoirs, load_existing(args.existing_sample), max_rows=MAX_ROWS)
    records = [build_candidate(pool[item["source_script"]][1], item["source_line_no"], source_sha, set(item["strata"])) for item in selected]
    pairs = discover_counterfactuals(records); omission = omission_audit(records, pairs); invariance = invariance_discovery(records)
    review_ledger = [{"pilot_sample_id": r["planner_view"]["sample_id"], "source_script": r["provenance"]["source_script"], "review_status": r["planner_view"]["review"]["status"], "field_reviews": {**{k: "pending" for k in r["planner_view"]["review"]["field_evidence"]}, "workflow.links": "pending", "workflow.repeat_semantics": "pending", "outputs": "pending"}, "notes": "", "reviewer": None} for r in records]
    summary = {"schema": PILOT_SCHEMA, "schema_status": "pilot_only", "training_admission": "not_granted", "production_samples": 0, "semantic_gold": False, "source": {"path": str(args.source), "sha256": source_sha, "rows_scanned": rows_scanned}, "selection": {"max_rows": MAX_ROWS, "target_per_stratum": TARGET_PER_STRATUM, "reservoir_size": RESERVOIR_PER_STRATUM, "reservoir_seed": reservoir_seed, "seen_counts": reservoir_seen_counts, "stop_reason": selection_stop_reason, "policy": "deterministic Algorithm-R reservoir sampling followed by maximal-marginal-gain selection with task diversity tie-break"}, "selected_rows": len(records), "unique_task_count": len({r["planner_view"]["task"] for r in records}), "strata_coverage": coverage, "strata_shortfalls": {s: max(0, TARGET_PER_STRATUM - coverage[s]) for s in STRATA}, "counterfactual_pairs": pairs, "omission_audit": omission, "implementation_invariance": invariance, "review_status_counts": dict(Counter(r["planner_view"]["review"]["status"] for r in records)), "stop_after_report": True}
    link_validation_errors = []
    leakage_counts = Counter()
    for record in records:
        for hit in record["planner_view"]["review"].get("leakage_hits", []):
            leakage_counts[hit] += 1
        try:
            validate_links(record["planner_view"])
        except ValueError as exc:
            link_validation_errors.append({"sample_id": record["planner_view"]["sample_id"], "error": str(exc)})
    cf_counts = Counter(item["status"] for item in pairs)
    omission_counts = Counter(item["status"] for item in omission)
    invariance_counts = Counter(item["status"] for item in invariance)
    review_counts = Counter(record["planner_view"]["review"]["status"] for record in records)
    outputs = {}

    def out(name, content):
        path = args.out_dir / name
        path.write_text(content, encoding="utf-8")
        outputs[name] = sha256_file(path)

    out("schema_pilot_records_v1.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records))
    out("schema_pilot_selection_v1.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in selected))
    out("schema_pilot_review_ledger_v1.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in review_ledger))
    out("schema_pilot_counterfactual_pairs_v1.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in pairs))
    out("schema_pilot_omission_audit_v1.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in omission))
    out("schema_pilot_invariance_v1.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in invariance))
    write_json(args.out_dir / "schema_pilot_summary_v1.json", summary)
    outputs["schema_pilot_summary_v1.json"] = sha256_file(args.out_dir / "schema_pilot_summary_v1.json")

    report = [
        "# GEE Semantic Planner Data v1 — Schema Pilot", "",
        "**Status: PILOT_ONLY / NOT_ADMITTED**", "",
        f"- Source rows scanned: `{rows_scanned}`",
        f"- Selected rows: `{len(records)}`",
        f"- Maximum rows: `{MAX_ROWS}`",
        f"- Unique selected tasks: `{len({r['planner_view']['task'] for r in records})}`",
        f"- Selection stop reason: `{selection_stop_reason}`",
        f"- Reservoir seed: `{reservoir_seed}`",
        f"- Reservoir size per stratum: `{RESERVOIR_PER_STRATUM}`",
        "- Selection: deterministic Algorithm-R reservoir + maximal-marginal-gain selection",
        "- G3 reconstruction: `not_performed`", "- Training/inference: `not_run`",
        "- Semantic gold: `false`", "", "## Strata",
    ]
    report.extend(f"- `{s}`: {coverage[s]}/{TARGET_PER_STRATUM} (shortfall={max(0, TARGET_PER_STRATUM - coverage[s])})" for s in STRATA)
    report.extend(["", "## Counterfactual discovery", f"- available: `{cf_counts['available']}`", f"- undetermined: `{cf_counts['undetermined']}`", f"- unavailable: `{cf_counts['unavailable']}`", "", "## Omission-collapse audit", f"- safe_omission: `{omission_counts['safe_omission']}`", f"- high-impact_collision: `{omission_counts['high-impact_collision']}`", f"- undetermined: `{omission_counts['undetermined']}`", f"- insufficient_pair_evidence: `{omission_counts['insufficient_pair_evidence']}`", "", "## Implementation invariance"])
    report.extend(f"- {status}: `{invariance_counts[status]}`" for status in ("available", "undetermined", "unavailable"))
    report.extend(["", "## Leakage audit", f"- records with leakage hits: `{sum(bool(r['planner_view']['review'].get('leakage_hits')) for r in records)}`", f"- leakage hit types: `{dict(leakage_counts)}`", "", "## Review status"])
    report.extend(f"- `{status}`: `{count}`" for status, count in sorted(review_counts.items()))
    report.extend(["", "## Link validation", f"- records checked: `{len(records)}`", f"- validation errors: `{len(link_validation_errors)}`", "", "## Provenance / identity", "- source_line_no recorded: `yes`", "- source_script recorded: `yes`", "- source_sha256 recorded per record: `yes`", "- duplicate source_script: `blocked on detection`", "- missing source_script: `blocked on detection`", "", "## Governance", "- `schema_status`: `pilot_only`", "- `training_admission`: `not_granted`", "- `production_samples`: `0`", "- `semantic_gold`: `false`", "- G0/G1/G2/G3 modification: `none`", "- model loading/inference/training: `not_performed`", "- RL/Blueprint-v3 freeze/scale-up: `not_performed`", "", "## Stop", "", "This is provisional schema-review evidence only. No training admission, G3 reconstruction, Blueprint-v3 freeze, RL, or scale-up is authorized."])
    report_path = args.out_dir / "schema_pilot_report_v1.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    outputs["schema_pilot_report_v1.md"] = sha256_file(report_path)
    write_json(args.out_dir / "schema_pilot_hash_ledger_v1.json", {"source_sha256": source_sha, "outputs": outputs, "hash_ledger_excludes_itself": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())