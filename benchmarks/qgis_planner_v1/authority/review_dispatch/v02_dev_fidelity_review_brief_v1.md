# Task-Fidelity Dual Review Brief — v0.2 DEV Task Drafts (15 entries)

You are an INDEPENDENT task-fidelity reviewer for a QGIS planner
benchmark's DEVELOPMENT split. You review 15 dev task drafts against
their gold DAGs and their sha-verified sources.

SCOPE DISCIPLINE: the DAGs' selection and admission were settled by
prior rounds -- do NOT re-adjudicate DAG identity, selection, or
eligibility. Your job is strictly the six fidelity questions.

## Inputs (read them)

1. `benchmarks/qgis_planner_v1/authority/v02_dev_task_derivation_draft_v1.jsonl`
   — 16 lines: 1 header + 15 task records (`task_text`, `task_scope`,
   `task_style`, `evidence`, provenance with source file name).
2. `benchmarks/qgis_planner_v1/authority/v02_dev_task_fidelity_worksheet_v2.jsonl`
   — the gold side per entry: `recovered_dag` (operators, l3_codes,
   edges), per-node `source_call_sites` (operator + line ranges),
   `parameter_strip.keys`, `topology_class`, `io_scope`. Join on
   `packet_entry_id`.
3. Source scripts (read-only, local mirrors). Source files named in
   the worksheet's `source_call_sites` context live under the crawl
   mirror `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\`
   (standard_v2 `script_0000xxx.py` under
   `QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\`;
   `script_XXXXX.py`/`script_XXXX.py` five/six-digit github_merge
   entries under `合并脚本\QGIS_merged_dedup_by_index\downloaded_scripts\`).
   One entry's primary source is not locally mirrored; its sha-verified
   supporting source is `script_4219.py` (same directory as
   github_merge) — judge from that file.
   Verify operand directions (e.g. for intersection/difference: which
   layer is INPUT, which OVERLAY) from the source code.

## The six questions (per task)

- Q1 source->task: does the task state ONLY what the source evidence
  supports (docstrings, comments, variables, call sites)?
- Q2 task->gold: do the task's operation semantics match the gold DAG's
  operators, edges, ordering, AND operand direction?
- Q3 scope: full_workflow tasks cover the whole recovered chain without
  smuggling surrounding custom code or the script's larger business
  goal?
- Q4 output: single-output tasks do not imply extra outputs?
- Q5 parameter stripping: no CRS values, distances, field names,
  parameter values, layer-specific literals?
- Q6 omission/addition: any gold operation with no task counterpart, or
  task semantics with no gold counterpart?

## Output format — STRICT

Output EXACTLY 15 JSON lines, one per task, nothing else:

{"review_id":"devfid-<pool_key first12>-<a|b>",
 "packet_entry_id":"<from draft>",
 "reviewer_id":"<your assigned id>",
 "decision":"accept"|"revise"|"reject",
 "verdicts":{"q1_source":true|false,"q2_gold":true|false,"q3_scope":true|false,
             "q4_output":true|false,"q5_stripping":true|false,"q6_omission_addition":true|false},
 "reason":"<concrete evidence, one to three sentences; cite source lines>"}

Decision policy: accept = all six pass; revise = a fixable text defect
(name the exact fix); reject = fundamental misstatement. Judge each
task independently.
