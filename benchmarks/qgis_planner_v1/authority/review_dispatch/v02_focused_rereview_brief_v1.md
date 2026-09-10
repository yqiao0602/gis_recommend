# Focused Dual Re-Review Brief — 5 Revised Task Texts (v0.2, Round 2)

You are an INDEPENDENT task-fidelity re-reviewer. Exactly FIVE task
texts were revised after the first dual review; you re-review only
these five, in their FINAL form.

## Scope — exactly these five entries

- recovered-302f34cdd7d87920
- recovered-361c5eb306dbc618
- recovered-429556807ae79c01
- recovered-4cb8772d44c58cc4
- recovered-8c87bab93cfc8fe5

## Inputs (read them)

1. `benchmarks/qgis_planner_v1/authority/v02_task_derivation_v3.jsonl`
   — the final task texts (`task_text`); the five entries also carry
   `dual_review_original_text` / `pre_review_original_text` (prior
   versions, for context only — judge the FINAL text).
2. `benchmarks/qgis_planner_v1/authority/v02_task_fidelity_worksheet_v3.jsonl`
   — the frozen gold side: `recovered_dag` (operators, l3_codes, edges),
   per-node `source_call_sites` (line ranges), `task_scope`,
   `output_cardinality`, `parameter_strip.keys`.
3. Source scripts (read-only, local mirrors):
   - script_0000478.py, script_0000588.py, script_0000912.py,
     script_0000903.py, script_0000736.py under
     `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\`

## The seven checks (per task)

- C1 task text <-> source evidence fidelity
- C2 task text <-> frozen gold DAG fidelity (operators, edges, order,
  operand direction -- e.g. for difference: which layer is the base
  being erased FROM and which is the overlay being erased)
- C3 scope correctness (full_workflow covers the chain; subchain_scoped
  stays inside the recovered sub-chain)
- C4 input/output completeness (multi-output tasks express both outputs;
  required business inputs the gold cannot express are named)
- C5 no business semantics invented that the source does not contain
- C6 no necessary gold semantics omitted
- C7 no parameter leakage (CRS values, distances, field names,
  parameter values, layer-specific literals)

## Forbidden

Do NOT propose modifying DAGs, sealed gold, Gate results, the supply,
or the benchmark protocol. Do NOT re-invent the task texts; if a text
fails a check, name the minimal fix, nothing more.

## Output format — STRICT

Output EXACTLY 5 JSON lines, one per entry, nothing else:

{"review_id":"focus-<first16 after 'recovered-'>-<a|b>",
 "packet_entry_id":"<one of the five>",
 "reviewer_id":"<your assigned id>",
 "decision":"accept"|"revise",
 "checks":{"c1_source":true|false,"c2_gold":true|false,"c3_scope":true|false,
           "c4_io":true|false,"c5_no_invention":true|false,
           "c6_no_omission":true|false,"c7_stripping":true|false},
 "reason":"<concrete evidence, one to three sentences; cite source lines>"}

Judge each text independently on its own evidence.
