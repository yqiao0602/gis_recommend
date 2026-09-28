# GEE Batch12 v8.9.9 Full Audit

Batch12 selected 5,000 source-disjoint GEE sources under frozen v8.9.9. The complete
AST/DAG, fidelity, typed mapping, facts, and proposal A/B replays produced identical
business artifacts. This report records the admission decision only; it does not
grant training data.

| Gate | Verified result |
| --- | --- |
| AST/DAG | 4,994 AST success, 6 parse failure; 227 passed, 119 partial, 4,648 fail-closed sources |
| Fidelity | 699 passed workflows from 313 sources; 44 exact duplicates |
| Typed mapping | 338 complete workflows from 166 sources; 132 canonical operators, 48 L3 codes |
| Facts | 335 fact bundles, 3 fact fail-closed, 228 deduplicated task-text candidates from 130 sources |
| Proposal | 105 pending proposals from 66 sources; 26 cross-batch duplicates and 47 reviewed-source overlaps excluded |
| Full-source audit | 50/50 SHA256 verified; 37 pass, 13 critical fail |

The hash-bound evaluator returned `failed_rule_repair_required`: precision `0.74`,
Wilson 95% lower `0.6044684273515117`, 13 critical failures, and zero training rows.
Loop/list/map/helper-created exported objects can lose output-relevant upstream
dataset, temporal/spatial filter, and transformation lineage while terminal calls
remain extractable.

Batch12 is not admitted. Repair only the proven upstream control-flow lineage gap,
replay from frozen AST/DAG, and replace the audit before reconsidering admission.

Remote evidence:

- `/home/qy/system_redesign/diagnostics/gee_batch12_5000_v8_9_9_20260810/audit_v8_9_9_full/evaluation_summary.json`
- `reviewed_audit_50.jsonl` SHA256: `20223a8d8e622c384501b77ba6bf87ee463789108a079b992c93ca36331a9572`
- evaluation summary SHA256: `5272ff020d179fde6a86676e652fecbeb876ab16dc017b41692bd6dbb24f338b`
