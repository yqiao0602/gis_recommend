# Task-Fidelity Dual Review Brief — v0.2 Pre-Review Final Task Set (Round 1)

You are an INDEPENDENT task-fidelity reviewer for a QGIS planner
benchmark. You review 21 final-candidate task texts against their gold
DAGs and their sha-verified sources.

SCOPE DISCIPLINE: the DAGs' existence, admission, and eligibility were
settled by prior review rounds -- do NOT re-adjudicate them. Your job
is strictly the six fidelity questions below, per task.

## Inputs (read them)

1. `benchmarks/qgis_planner_v1/authority/v02_task_derivation_v2.jsonl`
   — 22 lines: 1 header + 21 task records. Each has `task_text`,
   `task_scope` (full_workflow | subchain_scoped), `task_style`,
   `output_expression`, `evidence`, and provenance.
2. `benchmarks/qgis_planner_v1/authority/v02_task_fidelity_worksheet_v3.jsonl`
   — the gold side: per entry `recovered_dag` (operators, l3_codes,
   edges), `source_call_sites` (per-node operator + source line ranges),
   `output_cardinality`, `parameter_strip.keys`, `task_scope`.
   Join on `packet_entry_id`.
3. Source scripts: the worksheet gives each entry's source file name
   and line ranges. The files live under the local crawl mirror
   `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\`
   (for `script_XXXX.py` standard_v2 entries under
   `QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\`; for
   `script_XXXXX.py` github_merge entries under
   `合并脚本\QGIS_merged_dedup_by_index\downloaded_scripts\`). You may
   read them to verify, read-only.

## The six questions (per task)

- Q1 source->task: does the task state ONLY what the source evidence
  (docstrings, comments, variables, call sites) supports?
- Q2 task->gold: do the task's operation semantics match the gold DAG's
  operators, edges, and ordering (a reader could implement the DAG from
  the task, and the DAG satisfies the task)?
- Q3 scope: full_workflow tasks cover the whole recovered chain;
  subchain_scoped tasks describe ONLY the recovered sub-chain (no
  surrounding custom code, no original-script business goal)?
- Q4 output: single-output tasks do not imply extra outputs;
  multi-output tasks (marked multi) express BOTH outputs explicitly?
- Q5 parameter stripping: no CRS values, distances, field names,
  parameter values, or layer-specific literals leaked?
- Q6 omission/addition: any unacceptable semantic omission (a gold
  operation with no task counterpart) or addition (task semantics with
  no gold counterpart)?

## Output format — STRICT

Output EXACTLY 21 lines, one JSON object per task, nothing else:

{"review_id":"taskfid-<first16 of packet_entry_id after 'recovered-'>-<a|b>",
 "packet_entry_id":"<from task set>",
 "reviewer_id":"<your assigned id>",
 "decision":"accept"|"revise"|"reject",
 "verdicts":{"q1_source":true|false,"q2_gold":true|false,"q3_scope":true|false,
             "q4_output":true|false,"q5_stripping":true|false,"q6_omission_addition":true|false},
 "reason":"<one to three sentences of concrete evidence>"}

Decision policy: accept = all six pass; revise = a fixable text defect
(describe the exact fix); reject = the task fundamentally misstates
source, gold, scope, or leaks parameters beyond repair. Judge each task
independently.
