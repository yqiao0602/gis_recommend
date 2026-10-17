#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A-track P0: build Capability Profile v0_5 (OTB 109 cards completed).

Owner ruling (2026-10-17, recorded in OTB_EVIDENCE_SOURCING_REPORT_V1.md §5):
  - 109 OTB operators: evidence-driven completion pinned to upstream 8.1.2;
    per-field provenance recorded; unconfirmable fields stay unknown.
  - 6 operators (aggregate, genericregionmerging, imagetimeseriesgapfilling,
    multitempfilteringfilter, multitempfilteringoutcore,
    objectsradiometricstatistics): NOT completed, NOT guessed; registered as
    `provenance_unverified` (source & target-env availability unverified).
  - v0_5 is a NEW file; v0_4 is never modified.
  - NO top-level `description` key is written anywhere (S1 corpus guard);
    function descriptions go to layer_c_intent.text.
  - A1 keeps the frozen Top-10 candidate sets unchanged.

Mapping (mirrors the v0_4 layer_b schema exactly):
  parameters[] : {default, description, mandatory, name, type} (+ `choices`
                 list when the OTB param has AddChoice children - additive
                 field, ignored by the frozen full_card() renderer)
  outputs[]    : {description, name, type}
  n_required / n_optional computed from mandatory flags.
  layer_c_intent = {audited: false, source: "otb_8.1.2_SetDescription", text}

Outputs:
  route2_training/profile/qgis_operator_capability_profile_v0_5.json
  a_track_p0_v1/V05_BUILD_MANIFEST_V1.json   (per-oid provenance + checks)
  a_track_p0_v1/PROVENANCE_UNVERIFIED_V1.json (6-op registry + follow-up task)
"""
import hashlib
import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROFILE_DIR = REPO / "route2_training/profile"
V04 = PROFILE_DIR / "qgis_operator_capability_profile_v0_4.json"
V05 = PROFILE_DIR / "qgis_operator_capability_profile_v0_5.json"
A_DIR = (REPO / ("docs/reports/route2_p0_contract/plan_pipeline_v1/"
                 "planning_capability_audit_v1/diag50_v1/dx_v1/dx50_v1/"
                 "dx50_full_v1/a_track_p0_v1"))
EVIDENCE = A_DIR / "otb_evidence_812_v2.json"

UNVERIFIED = ["otb:aggregate", "otb:genericregionmerging",
              "otb:imagetimeseriesgapfilling", "otb:multitempfilteringfilter",
              "otb:multitempfilteringoutcore", "otb:objectsradiometricstatistics"]
PIN = {"tag": "8.1.2", "commit": "b3eb56034e371846c39ae249f837b6c14b3b5039",
       "mirror": "https://github.com/orfeotoolbox/OTB"}


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build_param(ev_p):
    item = {
        "name": ev_p["key"],
        "type": ev_p["otb_type"],
        "mandatory": bool(ev_p["required"]),
        "default": ev_p.get("default"),
        "description": ev_p.get("human_name") or None,
        "sources": ev_p.get("sources") or [],
    }
    if ev_p.get("choices"):
        item["choices"] = [{"key": k, "label": c.get("label"),
                            "description": c.get("description")}
                           for k, c in ev_p["choices"].items()]
    return item


def main():
    v04 = json.loads(V04.read_text(encoding="utf-8"))
    prof = {k: v for k, v in v04.items() if k != "_meta"}
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    apps = evidence["apps"]

    manifest_apps = {}
    manifest_apps_note = {}
    filled = 0
    for oid, entry in prof.items():
        if not oid.startswith("otb:"):
            continue
        if oid in UNVERIFIED:
            entry["provenance_status"] = "provenance_unverified"
            continue
        app = apps.get(oid.split(":", 1)[1])
        if app is None:
            raise SystemExit(f"FATAL: no evidence for {oid} (not marked unverified)")
        # SharedParameter placeholders = shares whose target could not be
        # resolved in any pinned source (OTB framework auto-params like
        # ram/elev/rand that QGIS does not expose). Excluded, not guessed.
        src_params = [p for p in app["parameters"]
                      if p["otb_type"] != "SharedParameter"]
        skipped_shared = sum(1 for p in app["parameters"]
                             if p["otb_type"] == "SharedParameter")
        params = [build_param(p) for p in src_params
                  if p["io_class"] in ("input", "literal", "unknown")]
        outputs = [{"name": p["key"], "type": p["otb_type"],
                    "description": p.get("human_name"),
                    "sources": p.get("sources") or []}
                   for p in src_params if p["io_class"] == "output"]
        n_req = sum(1 for p in params if p["mandatory"])
        entry["layer_b_params"] = {
            "n_required": n_req,
            "n_optional": len(params) - n_req,
            "parameters": params,
            "outputs": outputs,
        }
        entry["layer_c_intent"] = {
            "audited": False,
            "source": "otb_8.1.2_SetDescription",
            "text": app.get("description"),
        }
        # input_types_norm recomputed from evidence data-input classes
        # (v0_4's catalog-derived value was wrong for several OTB apps, e.g.
        # trainimagesclassifier showed 'literal' despite raster+vector inputs;
        # this field is only card-visible via full_card's `accepts:` line)
        in_classes = {p["normalized_type"] for p in src_params
                      if p["io_class"] == "input"}
        new_in = []
        if in_classes & {"raster", "raster_complex"}:
            new_in.append("raster")
        if "vector" in in_classes:
            new_in.append("vector")
        if not new_in and "file" in in_classes:
            new_in.append("literal")
        if new_in and entry.get("input_types_norm") != new_in:
            manifest_apps_note[oid] = {"input_types_norm_old":
                                       entry.get("input_types_norm"),
                                       "input_types_norm_new": new_in}
        if new_in:
            entry["input_types_norm"] = new_in
        filled += 1
        manifest_apps[oid] = {
            "otb_name": app["otb_name"],
            "source_files": app.get("source_files") or [],
            "n_parameters": len(params),
            "n_outputs": len(outputs),
            "n_choices_params": sum(1 for p in params if "choices" in p),
            "skipped_unresolved_shared_params": skipped_shared,
            "intent_text": app.get("description"),
            "unknown_io_params": sum(1 for p in src_params
                                     if p["io_class"] == "unknown"),
        }

    missing_unverified = [o for o in UNVERIFIED if o not in prof]
    if missing_unverified:
        raise SystemExit(f"FATAL: unverified oids absent from profile: {missing_unverified}")

    # ---------- assemble v0_5 (NEW file) ----------
    v05 = {}
    v05["_meta"] = dict(v04["_meta"])
    v05["_meta"]["layer_b_sources"] = list(v04["_meta"].get("layer_b_sources", [])) + [
        f"otb_upstream_v1 (OTB {PIN['tag']}, commit {PIN['commit'][:12]}..., "
        f"113 apps C++ macro extraction; 109 filled / 6 provenance_unverified)"]
    v05["_meta"]["a_track_v05"] = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_profile": "qgis_operator_capability_profile_v0_4.json",
        "base_profile_sha256": sha256_file(V04),
        "evidence_file": EVIDENCE.name,
        "evidence_sha256": sha256_file(EVIDENCE),
        "upstream_pin": PIN,
        "builder": "scripts/dx_a_track_build_v05_v1.py",
        "rules": [
            "v0_4 never modified; v0_5 is a new file",
            "no top-level description key written anywhere (S1 corpus guard)",
            "6 operators registered provenance_unverified (no params, no guesses)",
            "A1 keeps frozen Top-10 candidate sets; cards are the only variable",
        ],
    }
    for oid, entry in prof.items():
        v05[oid] = entry

    V05.write_text(json.dumps(v05, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    # ---------- validation ----------
    checks = {}
    checks["n_operators"] = len(v05) - 1  # minus _meta
    checks["n_operators_ok"] = checks["n_operators"] == 1291
    non_otel = {k: v for k, v in v05.items()
                if k != "_meta" and not k.startswith("otb:")}
    non_otb_v04 = {k: v for k, v in prof.items() if not k.startswith("otb:")}
    checks["non_otb_untouched"] = non_otel == non_otb_v04
    otb_entries = {k: v for k, v in v05.items() if k.startswith("otb:")}
    checks["otb_total"] = len(otb_entries)
    checks["otb_filled"] = sum(
        1 for e in otb_entries.values()
        if (e.get("layer_b_params") or {}).get("parameters"))
    checks["otb_filled_ok"] = checks["otb_filled"] == 109
    checks["otb_unverified_marked"] = sum(
        1 for e in otb_entries.values()
        if e.get("provenance_status") == "provenance_unverified")
    checks["otb_unverified_ok"] = checks["otb_unverified_marked"] == 6
    checks["top_level_description_keys"] = sum(
        1 for k, e in v05.items() if k != "_meta" and "description" in e)
    checks["description_guard_ok"] = checks["top_level_description_keys"] == 0
    checks["intent_set"] = sum(
        1 for e in otb_entries.values()
        if (e.get("layer_c_intent") or {}).get("source") == "otb_8.1.2_SetDescription")
    checks["v04_untouched_sha"] = sha256_file(V04)
    checks["v04_sha_matches_freeze"] = (
        sha256_file(V04) == json.loads(
            (A_DIR.parent / "A_TRACK_P0_HASH_FREEZE_V1.json").read_text(
                encoding="utf-8"))["profile"]["sha256"])
    checks["v05_sha256"] = sha256_file(V05)

    manifest = {
        "built_at": v05["_meta"]["a_track_v05"]["built_at"],
        "v05_path": "route2_training/profile/qgis_operator_capability_profile_v0_5.json",
        "provenance_per_app": manifest_apps,
        "input_types_norm_corrections": manifest_apps_note,
        "unverified_registry": "PROVENANCE_UNVERIFIED_V1.json",
        "checks": checks,
    }
    (A_DIR / "V05_BUILD_MANIFEST_V1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    prov = {
        "date": "2026-10-17",
        "status": "provenance_unverified",
        "definition": "算子来源及其在目标运行环境中的可用性未核实（非'已定性幽灵'）",
        "proven_facts": [
            "6 个 oid 在上游官方 6.6.2/7.4.2/8.1.2/9.1.1 四版本均无对应 application"
            "（逐 tag 实测 Modules/*/Applications 与 Modules/Applications）",
            "115 算子集合跨版本混合，不可能来自单一官方 release",
        ],
        "unproven": [
            "不存在于所有相关构建（remote module / 自定义构建未排除）",
            "一定来自 QGIS 官方 OTB 包的 remote module（QGIS 文档证实 OTB 需单独安装、"
            "支持多应用目录，但这不能定位 6 算子来源）",
        ],
        "operators": [{"oid": o,
                       "v04_state": "bare (no layer_b params/outputs, intent null)",
                       "v05_state": "unchanged + provenance_status marker; "
                                    "not treated as confirmed-executable"}
                      for o in UNVERIFIED],
        "follow_up_task": "核验目标 QGIS/OTB 安装环境：实际应用清单（otbApplicationLauncher"
                          "CommandLine --list）、QGIS OTB 配置的应用目录、构建来源/remote"
                          " modules；取得证据后判定为真实扩展算子或误入 Capability Profile "
                          "的记录",
        "a1_note": "A1 复用冻结 Top-10，候选集不因本发现改变",
    }
    (A_DIR / "PROVENANCE_UNVERIFIED_V1.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(checks, ensure_ascii=False, indent=1))
    if not all(v for k, v in checks.items()
               if k.endswith("_ok") or k == "non_otb_untouched"):
        raise SystemExit("VALIDATION FAILED")


if __name__ == "__main__":
    main()
