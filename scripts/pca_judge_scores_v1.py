#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA scoring Step-3 — DeepSeek semantic judging (owner round-16 approval).

Scope: 92 scoreable main rows (A 59 + C 33) + 6 B-prime diagnostics (translated).
85 degenerate rows are NOT judged (scoreable=False, reason=degenerate_response)
— they enter the response-rate layer only.
Rules: frozen rubric + pca_scoring_semantics_v1.md (evidence_source tagging,
apply-or-declare, underdetermined never penalized for value choice, presentation
separate, operator names unscored). API key from env PCA_JUDGE_KEY — never
stored in repo.
"""
import json, os, sys, time, hashlib, glob
import urllib.request

D = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/"
BATCH = "../pca_data_ref/pca_outputs_batch1/outputs"
OUT = D + "pca_judge_scores_v1.json"
API = "https://api.deepseek.com/v1/chat/completions"  # official (owner-provided key)
MODEL = "deepseek-flash"

FAMILY_SEM = {
 "RASTER_LOAD": "load the required satellite/raster dataset",
 "VECTOR_LOAD": "load the required vector dataset",
 "ATTRIBUTE_FILTER": "filter features/collections by attribute conditions",
 "TEMPORAL_FILTER": "filter the data by the specified date range",
 "BAND_SELECT": "select the spectral bands needed",
 "BAND_ARITHMETIC": "compute band arithmetic/index expressions",
 "MASKING": "apply masking to exclude invalid or unwanted pixels",
 "GEOMETRY_DEFINE": "define the geometry/region of interest",
 "SPATIAL_CLIP": "clip data to the spatial boundary",
 "AGGREGATION": "aggregate/reduce values over space or time",
 "CLASSIFICATION": "classify pixels/features into classes",
 "THRESHOLD_LOGIC": "apply threshold rules to separate conditions",
 "ITERATIVE_APPLY": "apply the operation iteratively over groups/items",
 "EXPORT_OUTPUT": "export/save the results",
}

def translate_blueprint(raw):
    """Deterministic B-prime restatement: blueprint JSON stages -> semantic steps."""
    try:
        s = raw[raw.index("{"):raw.rindex("}") + 1]
        try:
            bp = json.loads(s)
        except json.JSONDecodeError:
            # truncated (hit_cap) blueprint: cut to last complete stage object
            last = s.rfind("}")
            s2 = s[:last + 1]
            while s2.count("{") > s2.count("}"):
                s2 += "]}" if '"stages"' in s2 else "}"
            bp = json.loads(s2)
        steps = []
        for st in bp.get("stages", []):
            fam = st.get("family", "?")
            rep = int(st.get("repeat", 1) or 1)
            sem = FAMILY_SEM.get(fam, f"perform {fam.lower().replace('_', ' ')}")
            if rep > 1:
                steps.append(f"{sem} (repeated for each of the {rep} items/groups)")
            else:
                steps.append(sem)
        deps = "steps run in the listed order, each depending on the previous outputs" if steps else ""
        return "Plan:\n" + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)) + \
               (f"\nDependencies: {deps}." if steps else ""), None
    except Exception as e:
        return None, f"blueprint parse failed: {e}"

JUDGE_SYS = ("You are a strict GIS-workflow-plan evaluator. Score the MODEL PLAN against the GOLD "
             "SPEC using ONLY the stated rubric. Output ONLY valid JSON, no prose.")
JUDGE_TPL = """[TASK]
{task}

[GOLD SPEC]
required_outcome: {outcome}
required_constraints: {constraints}
required_capabilities: {capabilities}
acceptable_alternatives (non-exhaustive; equivalent valid routes allowed): {alternatives}
failure_conditions: {failures}
underdetermined_aspects (the model may freely choose values here; scoring checks DECLARATION/compatibility, never a specific value): {underdetermined}
presentation_requirements (separate delivery dimension, do not merge into planning quality): {presentation}

[MODEL PLAN]
{plan}

[RUBRIC]
Score and return JSON with exactly these keys:
{{"goal_sufficiency": 0-3 (0=cannot achieve the goal, 1=major gaps, 2=broadly achieves with gaps, 3=fully achieves),
"step_coverage": 0.0-1.0 (fraction of required capabilities/operations covered),
"missing_steps": [list of missing required operations],
"dependency_order": "pass|partial|fail" + brief reason,
"hard_constraint_check": [{{"constraint": "...", "verdict": "satisfied|violated|not_addressed", "evidence": "..."}}],
"extra_harmful_steps": [steps that would corrupt results or violate constraints],
"undeclared_parameter_use": "none | <list parameter choices made WITHOUT stating them when the rubric requires declaration>",
"presentation_done": "yes|partial|no|not_applicable",
"constraint_following_vs_planning": "one sentence: which elements were explicitly specified by the task vs which the model had to plan itself",
"evidence_notes": "short evidence quotes/anchors",
"assessable": true|false (false only if the plan has no interpretable content at all)}}

Scoring rules: task-explicit requirements are hard constraints; unspecified values are NEVER penalized for value choice (only for missing required declaration); acceptable alternatives are valid; operator/API names are not scored; presentation is separate."""

def call_judge(payload, key, retries=3):
    body = json.dumps({"model": MODEL, "temperature": 0, "max_tokens": 8000,
                       "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": JUDGE_SYS},
                                    {"role": "user", "content": payload}]}).encode()
    for a in range(retries):
        try:
            req = urllib.request.Request(API, data=body, headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                out = json.loads(resp.read())
            return out["choices"][0]["message"]["content"], None
        except Exception as e:
            if a == retries - 1:
                return None, str(e)[:200]
            time.sleep(15 * (a + 1))

def main():
    key = os.environ.get("PCA_JUDGE_KEY")
    assert key, "set PCA_JUDGE_KEY env var"
    A = json.load(open(D + "pca_a_gold_worksheet_v1.json", encoding="utf-8"))
    C = json.load(open(D + "pca_c_group_tasks_gold_v2.json", encoding="utf-8"))
    B = json.load(open(D + "pca_b_gold_worksheet_v2.json", encoding="utf-8"))
    parse = json.load(open(D + "pca_parse_health_v1.json", encoding="utf-8"))
    ph = {(r["arm"], r["task_id"]): r for r in parse["rows"]}
    gold = {}
    for src in (A["rows"], B["rows"], C["rows"]):
        for r in src:
            tid = r.get("task_id") or r.get("wid")
            for arm in ("A_base", "B_stage1", "C_stage1_tool"):
                gold[(arm, tid)] = r
    files = sorted(glob.glob(BATCH + "/*/*/run_001.json"))
    jobs = []
    for f in files:
        r = json.load(open(f, encoding="utf-8"))
        phr = ph.get((r["arm"], r["task_id"]))
        if r["arm"] == "Bprime_diag":
            jobs.append((r, None, "bprime"))
        elif phr and phr["scoreable"]:
            jobs.append((r, gold[(r["arm"], r["task_id"])], "main"))
        else:
            pass  # degenerate: not judged
    print(f"judging {len(jobs)} rows (92 main expected + 6 bprime)")
    results, errs = [], []
    # incremental checkpoint: survives session/process interruption
    done_keys = set()
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8"))
            results = prev.get("results", [])
            errs = prev.get("errors", [])
            if all("401" in (e.get("error") or "") for e in errs) and errs:
                errs = []  # stale 401 errors from dead endpoint; fresh run re-attempts all
            done_keys = {(r["arm"], r["task_id"]) for r in results
                         if not r["judge"].get("_parse_error")}
            results = [r for r in results if not r["judge"].get("_parse_error")]
            # purge stale errors from dead endpoints (all-401 blocks) and
            # transient SSL/parse failures — they will be re-attempted below
            errs = [e for e in errs if "401" not in (e.get("error") or "")
                    and "blueprint parse" not in (e.get("error") or "")]
            print(f"resuming: {len(results)} already judged, "
                  f"{len(errs)} transient errors queued for retry", flush=True)
        except Exception:
            pass
    for i, (r, g, kind) in enumerate(jobs):
        if (r["arm"], r["task_id"]) in done_keys:
            continue
        if kind == "bprime":
            plan, err = translate_blueprint(r["raw_output"])
            if plan is None:
                errs.append({"task_id": r["task_id"], "arm": r["arm"], "error": err})
                continue
            task_text = BP_TASKS.get(r["task_id"], "(task text see frozen pack)")
            payload = JUDGE_TPL.format(task=task_text, outcome="(diagnostic translation; structural quality focus)",
                                       constraints="[]", capabilities="[]", alternatives="[]",
                                       failures="[]", underdetermined="[]", presentation="[]", plan=plan)
        else:
            payload = JUDGE_TPL.format(
                task=r["task_id"] and gold[(r["arm"], r["task_id"])]["task_text"],
                outcome=g["required_outcome"],
                constraints=json.dumps(g["required_constraints"], ensure_ascii=False),
                capabilities=json.dumps(g["required_capabilities"], ensure_ascii=False),
                alternatives=json.dumps(g["acceptable_alternatives"], ensure_ascii=False),
                failures=json.dumps(g["failure_conditions"], ensure_ascii=False),
                underdetermined=json.dumps(g["underdetermined_aspects"], ensure_ascii=False),
                presentation=json.dumps(g.get("presentation_requirements", []), ensure_ascii=False),
                plan=r["raw_output"])
        out, err = call_judge(payload, key)
        if out is None:
            errs.append({"task_id": r["task_id"], "arm": r["arm"], "error": err})
            continue
        try:
            js = json.loads(out)
        except Exception:
            # tolerant extraction: strip fences, take first { to last }
            try:
                s = out.find("{")
                e = out.rfind("}")
                js = json.loads(out[s:e + 1])
            except Exception:
                js = {"_raw": out, "_parse_error": True}
        results.append({"task_id": r["task_id"], "arm": r["arm"], "kind": kind,
                        "judge": js,
                        "judge_input_sha": hashlib.sha256(payload.encode()).hexdigest()[:16]})
        if (i + 1) % 10 == 0:
            json.dump({"_meta": {"n_judged": len(results), "n_errors": len(errs),
                                 "model": MODEL, "checkpoint": True},
                       "results": results, "errors": errs},
                      open(OUT, "w", encoding="utf-8", newline=""), ensure_ascii=False, indent=1)
            print(f"{i + 1}/{len(jobs)} judged (checkpointed)", flush=True)
    payload_out = {"_meta": {"n_judged": len(results), "n_errors": len(errs),
                             "model": MODEL, "temperature": 0,
                             "rubric_sha": hashlib.sha256(JUDGE_TPL.encode()).hexdigest()[:16]},
                   "results": results, "errors": errs}
    blob = json.dumps(payload_out, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("judged:", len(results), "errors:", len(errs))
    print("file_sha256:", hashlib.sha256(blob.encode()).hexdigest()[:16])

# B-prime diagnostic task texts (from frozen pack, inline to avoid repackaging)
_bp = json.load(open(D + "pca_gen_pack_bprime_v1.json", encoding="utf-8"))
BP_TASKS = {t["task_id"]: t["task_text"] for t in _bp["tasks"]}

if __name__ == "__main__":
    main()
