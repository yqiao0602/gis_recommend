# GEE Workflow Rulefix2 Risk Review

## Scope

This review covers the stable 50 workflow identities in the rulefix2 risk packet.
Every decision checks exact source SHA and the complete output-relevant workflow
across dataset, temporal, spatial, transformation, output, and task-text fidelity.
It does not grant validation, test, production, or model-training admission.

Authority:

- Facts/text: `/home/qy/system_redesign/diagnostics/gee_workflow_task_facts_pilot500_20260730_rulefix2_a`
- Source root: `/home/yll/GEE/Data` (read-only)
- Review identity: `(source_sha256, workflow_id)`; `review_index` is non-authoritative

## Result

| Decision | Count |
| --- | ---: |
| `pass` | 47 |
| `defer_source_ambiguity` | 3 |
| `needs_rule_fix` | 0 |

All 50 source byte hashes match the packet. The 47 passes have complete and ordered
source-backed chains after deterministic rule replay. One pass,
`data60000/script_54282.txt` / `output-workflow-1`, contains 155 operators and must be
routed to a current-loader length sidecar rather than direct V4 admission.

## Deferred Workflows

| Source | Workflow | Reason |
| --- | --- | --- |
| `data150000/script_148504.txt` | `output-workflow-1` | Export `region` is an `ee.Image`; the intended spatial contract is not provable. |
| `data230000/script_222751.txt` | `output-workflow-1` | Reused `dataset` bindings require version-aware resolution to prove the merged FeatureCollection spatial lineage. |
| `data400000/script_403940.txt` | `output-workflow-1` | AOI is a placeholder project asset and cannot support a complete spatial input fact. |

## Admission Boundary

Risk review is closed, but training rows remain zero. The next gate is a dedicated
complete-workflow train-only schema and exporter with fact/chain/L3/source-lineage
validation. Direct current-loader eligibility is at most 46 reviewed rows: 47 pass
minus the 155-step length-sidecar row. This bounded review does not authorize the
remaining 126 unreviewed canonical candidates.
