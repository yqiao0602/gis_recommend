#!/usr/bin/env python3
"""Four-layer reconciliation audit for six priority GEE scripts.

This is a bounded, read-only diagnostic. It does not re-run the extractor,
modify G0, generate training data, or make semantic-gold decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

G0_SHA = "09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2"
SCRIPTS = {
    "script_302840": ("21_predict_vegetation_cover_components", "data300000/script_302840.txt"),
    "script_269131": ("27_fire_susceptibility", "data270000/script_269131.txt"),
    "script_36595": ("30_rusle_soil_loss", "data40000/script_36595.txt"),
    "script_275285": ("33_land_surface_temperature_inversion", "data280000/script_275285.txt"),
    "script_405410": ("35_ancient_road_cost_surface", "data400000/script_405410.txt"),
    "script_93009": ("38_urban_expansion_change_detection", "data100000/script_93009.txt"),
}

# Evidence units are audit hypotheses, not labels. Regex matches are retained as
# source evidence and never promoted to Planner semantic gold.
UNITS = {
    "script_302840": [
        ("target_variable_loop", r"for\s*\(|coi\d*\s*=|target variable|for each target", r"map|iterate"),
        ("model_training", r"\.train\s*\(|smileRandomForest|Classifier", r"Classifier|train"),
        ("prediction_sampling", r"sampleRegions|sample\s*\(|predLst|classify\s*\(", r"sampleRegions|sample|classify"),
        ("target_export_filter", r"Export\.table|toCloudStorage|lsNDVI|mdNDVI", r"Export|sampleRegions|Filter"),
    ],
    "script_269131": [
        ("environmental_inputs", r"temperature|humidity|wind|precipitation|radiation|population|elevation|slope", r"ImageCollection|Terrain|Image"),
        ("factor_transform", r"\.log\s*\(|multiply\s*\(|pi_[A-Za-z]+", r"Number|multiply|log"),
        ("weighted_factor_fusion", r"Fire[_ ]Sus|pi_|\.add\s*\(|\.subtract\s*\(", r"add|multiply|sum"),
        ("susceptibility_classification", r"Very Low|Very High|classif|reclass|classified", r"Fire_Sus|where|classify|remap|gte|lte"),
        ("regional_output", r"reduceRegion|reduceRegions|Export|chart|visual", r"reduceRegion|reduceRegions|Export|selfMask"),
    ],
    "script_36595": [
        ("r_factor", r"\bR\b|R\s*=|rainfall|precipitation", r"multiply|add|Image"),
        ("k_factor", r"\bK\b|soil erodibility|soil\.expression", r"expression|Image"),
        ("ls_factor", r"\bLS\b|slope|slope length|steepness", r"Terrain\.slope|multiply|pow"),
        ("c_factor", r"\bC\b|NDVI|vegetation cover", r"normalizedDifference|multiply|exp"),
        ("p_factor", r"\bP\b|land management|lulc", r"expression|Image"),
        ("rusle_product", r"soil_loss|R\.multiply\(K|multiply\(LS|RUSLE", r"multiply"),
        ("classification_statistics", r"SL_class|reduceRegion|reduceRegions|area statistics", r"reduceRegion|reduceRegions|group"),
    ],
    "script_275285": [
        ("cloud_shadow_mask", r"pixel_qa|cloudShadow|cloudsBitMask|updateMask", r"select|bitwiseAnd|updateMask"),
        ("composite", r"\.median\s*\(|composite", r"median|ImageCollection"),
        ("ndvi", r"normalizedDifference|\bNDVI\b", r"normalizedDifference"),
        ("fractional_vegetation", r"\bFV\b|fractional vegetation|pow\s*\(ee\.Number\(2", r"pow|subtract|divide"),
        ("emissivity", r"\bEMM\b|emissivity", r"multiply|add|rename"),
        ("thermal_band", r"B10|thermal", r"select|multiply"),
        ("lst_expression", r"\bLST\b|radiative|expression\s*\(", r"expression|rename"),
    ],
    "script_405410": [
        ("slope_altitude_cost", r"cost_slope|cost_altitude|slope|altitude|DSM", r"Terrain.slope|pow|multiply"),
        ("snow_cost", r"cost_snow|NDSI|snow", r"MOD10A1|filter|reduce"),
        ("water_barriers", r"mask_sea|cost_surface_water|water barrier|MonthlyRecurrence", r"MOD44W|MonthlyRecurrence|remap"),
        ("reservoir_mask", r"mask_reservoirs|reservoir|GRanD", r"FeatureCollection|paint|remap"),
        ("potable_water_accessibility", r"potable|water_accessibility|accessibility", r"water|reduce|distance"),
        ("cost_fusion", r"costs_raw|cost surface|multiply|add|divide", r"multiply|add|divide"),
        ("normalization_export", r"0.?255|uint8|toUint8|Export|costs_max_assigned", r"toUint8|Export|clamp|divide|multiply"),
    ],
    "script_93009": [
        ("cloud_filter", r"applyFilterCloud|cloud", r"filter|applyFilterCloud"),
        ("frequency_filter", r"applyFilterFreq|frequency|freq_antes|freq_depois", r"applyFilterFreq|reduce"),
        ("image_collection_conversion", r"toImageCollection|imc", r"toImageCollection|ImageCollection"),
        ("incidence_iteration", r"incidence|iterate|classification0|classification1", r"iterate|where|add"),
        ("year_extraction", r"get_image_year|1985|2018|2017|1999|2000", r"select|remap"),
        ("recent_filter", r"applyFilterRecent|image_recent", r"applyFilterRecent|filter"),
        ("change_outputs", r"Map.addLayer|incidents|freq_|urban|Export", r"addLayer|Export"),
    ],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_g0(path: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            script = row.get("script")
            if script in SCRIPTS:
                if script in rows:
                    raise ValueError(f"duplicate selected G0 script: {script}")
                rows[script] = {"line_no": line_no, "row": row}
    missing = sorted(set(SCRIPTS) - set(rows))
    if missing:
        raise ValueError(f"selected scripts missing from G0: {missing}")
    return rows


def tokens(value: Any) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in str(value).split(" -> ") if part.strip()]


def first_span(pattern: re.Pattern[str], text: str) -> dict[str, Any] | None:
    match = pattern.search(text)
    if not match:
        return None
    line = text[:match.start()].count("\n") + 1
    return {"start_line": line, "end_line": line, "matched": match.group(0)}


def classify_mismatch(source_present: bool, canonical_present: bool, raw_present: bool, rle_present: bool) -> tuple[str, str]:
    if not source_present:
        return "unknown", "no raw-source evidence for this unit"
    if source_present and not canonical_present:
        return "unknown", "raw source exists but canonical/parser mapping layer is unavailable"
    if source_present and canonical_present and not raw_present:
        return "unknown", "raw source and canonical evidence exist; parser/mapping-to-semantic layer not independently bound"
    if raw_present and not rle_present:
        return "representation_gap", "unit appears in raw semantic chain but not in RLE output"
    if raw_present and rle_present:
        return "representation_gap", "unit survives as a coarse category; identity/dependency binding requires review"
    return "unknown", "insufficient layer evidence"


def build_ledger(raw_dir: Path, g0_rows: dict[str, dict[str, Any]], parser_dir: Path | None = None) -> list[dict[str, Any]]:
    parser_evidence: dict[str, dict[str, Any]] = {}
    if parser_dir is not None:
        for script in SCRIPTS:
            artifact = parser_dir / f"{script}_parser_evidence_v1.json"
            if artifact.is_file():
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                parser_evidence[script] = payload["evidence"]
    ledger = []
    for script, (label, relative) in SCRIPTS.items():
        raw_path = raw_dir / relative
        raw_text = raw_path.read_text(encoding="utf-8")
        g0 = g0_rows[script]["row"]
        line_no = g0_rows[script]["line_no"]
        canonical = str(g0.get("gee_canonical_chain", ""))
        canonical_tokens = tokens(canonical)
        raw_chain = tokens(g0.get("semantic_chain_raw"))
        rle_chain = tokens(g0.get("semantic_chain_rle"))
        evidence = parser_evidence.get(script)
        core_callees = []
        if evidence:
            calls = evidence.get("ordered_calls", [])
            core_callees = [calls[i - 1].get("raw_callee") or "" for i in evidence.get("core_operator_chain", []) if 0 < i <= len(calls)]
        for unit_name, source_regex, canonical_regex in UNITS[script]:
            source_match = first_span(re.compile(source_regex, re.I), raw_text)
            source_present = bool(source_match)
            unit_rx = re.compile(canonical_regex, re.I)
            # Layer 2: parser (v2.3.2) core chain, matched by the unit's canonical-layer regex.
            parser_hits = [callee for callee in core_callees if unit_rx.search(callee)] if evidence else []
            parser_present = bool(parser_hits)
            # Layer 3: G0 canonical chain (built by the older production pipeline).
            canonical_match = first_span(unit_rx, canonical)
            canonical_present = bool(canonical_match)
            # Layer 4/5: G0 semantic raw chain and RLE, matched by unit keyword.
            unit_keyword = unit_name.split("_")[0]
            raw_semantic_match = bool(re.search(re.escape(unit_keyword), " ".join(raw_chain), re.I))
            rle_semantic_match = raw_semantic_match and bool(re.search(re.escape(unit_keyword), " ".join(rle_chain), re.I))
            # Layered classification, fail-closed. A unit is only classified when
            # every required upstream layer is positively evidenced.
            if not source_present:
                mismatch, note = "unknown", "no raw-source evidence for this unit"
            elif evidence is None:
                mismatch, note = "unknown", "parser evidence unavailable for this script"
            elif not parser_present:
                mismatch, note = "unknown", "source exists but parser core chain has no callee matching the unit's canonical pattern; matcher may be too narrow"
            elif not canonical_present:
                mismatch, note = "extraction_loss", "source parsed (v2.3.2) but G0 canonical chain lacks the operation; lost in the production chain-construction pipeline"
            elif not raw_semantic_match:
                mismatch, note = "mapping_loss", "operation present in G0 canonical chain but absent from semantic chain (dropped or over-coarsened during category mapping)"
            elif not rle_semantic_match:
                mismatch, note = "rle_loss", "unit present in raw semantic chain but lost after RLE/run-cap"
            else:
                mismatch, note = "representation_gap", "operation survives all layers as a coarse category; identity/dependency binding is missing"
            ledger.append({
                "source_script": script,
                "source_line_no": line_no,
                "source_sha256": sha256_file(raw_path),
                "review_label": label,
                "unit_id": f"{script}:{unit_name}",
                "task_claim": g0.get("instruction", ""),
                "expected_semantic_unit": unit_name,
                "raw_source_evidence": {"start_line": source_match["start_line"] if source_match else None, "end_line": source_match["end_line"] if source_match else None, "excerpt_hash": hashlib.sha256((source_match["matched"] if source_match else "").encode()).hexdigest(), "status": "supported" if source_match else "unknown", "matched": source_match["matched"] if source_match else None},
                "parser_layer": {"call_ordinals": [], "status": "present" if evidence else "unavailable", "evidence": {"core_chain_length": len(core_callees), "matching_callees": parser_hits[:8], "match_count": len(parser_hits)}},
                "mapping_layer": {"canonical_tokens": [canonical_match["matched"]] if canonical_match else [], "mapped_semantic_categories": [], "unmapped_tokens": [], "status": "present_g0_canonical_chain" if canonical else "unavailable"},
                "semantic_chain_raw_layer": {"tokens": raw_chain, "contains_unit": "yes" if raw_semantic_match else "no", "status": "present" if raw_chain else "missing"},
                "rle_layer": {"tokens": rle_chain, "contains_unit": "yes" if rle_semantic_match else "no" if raw_semantic_match else "not_applicable", "repeat_or_run_cap_effect": "run_cap" if g0.get("run_cap_applied") else "rle_only" if len(raw_chain) != len(rle_chain) else "none"},
                "dependency_evidence": {"upstream_units": [], "downstream_units": [], "branch_or_merge": "unknown"},
                "mismatch_class": mismatch,
                "evidence_status": "supported" if source_match and evidence else "unknown",
                "notes": note,
            })
    return ledger


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--g0", type=Path, required=True)
    parser.add_argument("--parser-dir", type=Path, help="directory with per-script parser evidence artifacts")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    g0_rows = load_g0(args.g0)
    ledger = build_ledger(args.raw_dir, g0_rows, parser_dir=args.parser_dir)
    ledger_path = args.out_dir / "reconciliation_ledger_v1.jsonl"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    counts = Counter(row["mismatch_class"] for row in ledger)
    summary = {"schema": "gee_six_script_extractor_reconciliation_v1", "source_g0_sha256": sha256_file(args.g0), "scripts": sorted(SCRIPTS), "ledger_rows": len(ledger), "mismatch_counts": dict(counts), "per_script_units": {script: {row["expected_semantic_unit"]: row["mismatch_class"] for row in ledger if row["source_script"] == script} for script in sorted(SCRIPTS)}, "parser_layer_policy": "per-script AST evidence supplied" if args.parser_dir else "unavailable unless explicit per-script AST evidence is supplied", "training_admission": "not_granted", "production_samples": 0, "semantic_gold": False, "g0_modified": False, "stop_after_report": True}
    write_json(args.out_dir / "reconciliation_summary_v1.json", summary)
    report = ["# Six-Script GEE Extractor Reconciliation", "", "**Status: DIAGNOSTIC_ONLY / NOT_ADMITTED**", "", f"- Scripts: {len(SCRIPTS)}", f"- Ledger rows: {len(ledger)}", f"- G0 SHA-256: `{summary['source_g0_sha256']}`", "", "## Mismatch counts"]
    report.extend(f"- `{key}`: `{value}`" for key, value in sorted(counts.items()))
    report.extend(["", "## Per-script units"])
    for script in sorted(SCRIPTS):
        report.append(f"### {script} ({SCRIPTS[script][0]})")
        for row in ledger:
            if row["source_script"] == script:
                report.append(f"- `{row['expected_semantic_unit']}`: `{row['mismatch_class']}` (source evidence: `{row['evidence_status']}`)")
    report.extend(["", "## Layer policy", "", "Raw source evidence and G0 canonical/semantic fields are compared without rerunning a full extractor. Parser-layer evidence is marked unavailable unless an explicit per-script AST artifact is supplied. Fail-closed rule: without parser-layer evidence, most units cannot be classified beyond `unknown`.", "", "## Stop", "", "This is diagnostic evidence only; no G0/G1/G2/G3 modification, training, inference, G3 reconstruction, Blueprint-v3 freeze, or RL was performed."])
    report_path = args.out_dir / "reconciliation_report_v1.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    outputs = {path.name: sha256_file(path) for path in (ledger_path, args.out_dir / "reconciliation_summary_v1.json", report_path)}
    write_json(args.out_dir / "reconciliation_hash_ledger_v1.json", {"source_g0_sha256": summary["source_g0_sha256"], "raw_script_sha256": {script: sha256_file(args.raw_dir / relative) for script, (_, relative) in SCRIPTS.items()}, "outputs": outputs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
