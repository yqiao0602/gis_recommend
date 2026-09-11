# Task-Fidelity Dual Review Brief — v0.2 FINAL Variant Drafts (9 entries)

You are an INDEPENDENT task-fidelity reviewer. You review 9 final-split
variant task drafts against their gold DAGs and sha-verified sources.

SCOPE DISCIPLINE: DAG identity, selection, and admission are frozen --
do NOT re-adjudicate them. Your job is strictly the six fidelity
questions. Note two entry groups:
  - three NEW first variants (571c057b7e, 79dde3ac5c, 303d4eb115):
    review source->task and task->gold fully;
  - six SECOND variants (style-paired counterparts of already-adjudicated
    first variants): the first variant's fidelity is settled; your job
    is whether THIS variant text independently satisfies the six
    questions (especially Q2 operand directions and Q4 outputs).

## Inputs (read them)

1. `benchmarks/qgis_planner_v1/authority/v02_final_variant_draft_v1.jsonl`
   — 10 lines: header + 9 drafts (`task_text`, `task_style`, `evidence`,
   `variant_role`).
2. Gold + source evidence:
   - for the 6 pool DAGs, the canonical structures are in
     `benchmarks/qgis_planner_v1/authority/v02_dev_final_selection_ledger_v1.json`
     (`final_side.pool_admitted`) and the recovered ones' full evidence in
     `v02_task_fidelity_worksheet_v3.jsonl` (join by 10-hex key prefix);
   - sources (sha-verified mirrors, read-only): script_0000478.py,
     script_0000912.py, script_0007090.py under
     `E:\...\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\`;
     script_0001006.py same directory; script_0002969.py under
     `...\github_qgis_workflow\downloaded_scripts\`; script_0004149.py under
     `...\github_qgis_workflow_A类\downloaded_scripts\` (two same-name
     decoys exist elsewhere -- use ONLY the A类 one, and verify call
     sites match the operators).
3. The adjudicated first variants for the reuse pairs are in
   `v02_task_derivation_v4.jsonl` (for orientation only; do not judge
   them again).

## The six questions (per task)

Q1 source->task fidelity; Q2 task->gold (operators, edges, order,
OPERAND DIRECTIONS for intersection/difference/join); Q3 scope
(no business-goal smuggling, no surrounding custom code); Q4 outputs
(multi-output tasks express both; single-output do not imply extra);
Q5 parameter stripping; Q6 omission/addition.

## Output format — STRICT

Output EXACTLY 9 JSON lines, nothing else:

{"review_id":"finvar-<pool_key first10>-<variant>-<a|b>",
 "pool_key":"<10-hex>", "variant":"v1"|"v2",
 "reviewer_id":"<your assigned id>",
 "decision":"accept"|"revise"|"reject",
 "verdicts":{"q1_source":true|false,"q2_gold":true|false,"q3_scope":true|false,
             "q4_output":true|false,"q5_stripping":true|false,"q6_omission_addition":true|false},
 "reason":"<concrete evidence, one to three sentences; cite source lines>"}
