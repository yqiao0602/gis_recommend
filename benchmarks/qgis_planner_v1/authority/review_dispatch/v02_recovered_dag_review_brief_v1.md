# Independent QGIS Graph Review Brief — v0.2 Recovered DAGs (Round 1)

You are an INDEPENDENT technical QGIS graph reviewer. You are reviewing
24 recovered candidate DAGs for a GIS operator-recommendation benchmark.
Work strictly from the evidence provided; do not assume anything not in
the evidence. You may read the referenced source files to verify, but
you must not modify anything.

## Input files (read them)

1. `benchmarks/qgis_planner_v1/authority/v02_recovered_dag_review_packet_v1.jsonl`
   — 25 lines: 1 header + 24 packet entries. Each entry has:
   `packet_entry_id`, `normalized_dag_key`, `original_action_gate`,
   `supporting_records`, `discovery_refs`, `dag` (operators, l3_codes,
   edges, graph_size_stratum, topology_class, has_fanout, has_fanin),
   `c_rule` (anchor_l3, anchor_name, covered_l3, covered_names, verdict),
   `source_evidence` (source_path, source_root_id, source_sha256,
   source_snippet_capped, task_text_admission, reason_summary),
   `task_fidelity_evidence`, `review_checklist`.
2. `benchmarks/qgis_planner_v1/authority/v02_supported_family_roster.json`
   — the frozen roster: 20 SUPPORTED, 8 DEFERRED, 22 OUT_OF_SCOPE families.

## Context you must know

- These 24 DAGs were recovered from discovery records gated by
  `action=review_api_sidecar` (held back pending review, never rejected)
  and passed four mechanical gates: strict operator mapping, graph
  validity, a nine-index exclusion check against training/exposure
  sources, and eligibility rule C (anchor in SUPPORTED; intermediate
  families in SUPPORTED-union-DEFERRED; nothing in OUT_OF_SCOPE).
- Your review is the missing semantic layer. Mechanical passage does NOT
  mean admission.
- The original gate reasons (in `reason_summary`) include
  `blocked_custom_transform` / `blocked_downstream_transform` and lists
  of intermediate data-transform calls (e.g. pandas operations) in the
  source scripts: judge per DAG whether the recovered operator DAG still
  faithfully represents the workflow, or whether the custom transforms
  make the DAG an under-representation that should stay gated.
- Source paths are local; some may not resolve. The capped source
  snippet plus sha256 in the packet is primary evidence. Where a source
  path does resolve, you may open it read-only to check the operator
  call sites and dependency edges.

## Per-DAG checks (all seven)

1. SOURCE — is the QGIS code evidence real and sufficient for this graph?
2. ACTION — was the original gate reason semantically valid or overcautious?
3. DAG — do the operators and edges match the source evidence (a real,
   executable workflow)?
4. TOPOLOGY — is `topology_class` correct given `edges`? (linear = no
   fan-in/fan-out; pure_merge = fan-in only; pure_branch = fan-out only;
   hybrid = both.)
5. FAMILY — is the anchor in SUPPORTED, and is every covered family in
   SUPPORTED or DEFERRED (rule C)?
6. ORIGINAL REASON — if the record was gated, does that reason still
   disqualify it?
7. TASK FIDELITY — can a faithful, parameter-free natural-language task
   be derived from this source (per a source-derived task policy)?

## Decision policy

- `accept` — all seven checks pass; the DAG may proceed to task-text
  derivation.
- `revise` — a fixable defect exists (e.g. one wrong edge, a recoverable
  under-representation); describe exactly what must change.
- `reject` — a fatal defect: source does not support the graph, rule C
  is actually violated, or the original gate reason is correct and
  disqualifying.

## Output format — STRICT

Output EXACTLY 24 lines, one JSON object per packet entry, nothing else
(no prose, no markdown fences). Fields:

{"review_id": "recovered-<first16 of normalized_dag_key>-<a|b>-v1",
 "packet_entry_id": "<from packet>",
 "reviewer_id": "<your assigned reviewer id>",
 "reviewed_at": "<ISO 8601 now>",
 "decision": "accept" | "revise" | "reject",
 "reason": "<one to three sentences of concrete evidence>",
 "checked_operator_ids": ["<every operator you verified>"],
 "checked_links": [["s","t"], ...],
 "strata_verdicts": {"graph_size_stratum": true|false, "topology": true|false, "family_rule_c": true|false},
 "exclusion_verdict": "original_reason_still_valid" | "overcautious" | "fatal",
 "task_fidelity_verdict": "derivable" | "uncertain" | "not_derivable"}

Judge each DAG independently on its own evidence. Do not let one
decision bias another.
