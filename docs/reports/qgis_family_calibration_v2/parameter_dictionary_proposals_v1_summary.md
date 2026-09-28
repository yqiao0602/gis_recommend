# Parameter Dictionary Proposal Calibration v1

## Scope

- Family: `parameter_dictionary`
- Rule: `resolve-single-scope-parameter-dictionary-v1`
- Input: `docs/reports/qgis_family_calibration_v2/review_60_v1.jsonl`
- Reviewed records: 30
- Authority check: each `source_path` was read through `qy@10.191.2.38`; 30/30 remote SHA-256 values match `source_sha256`.
- Status: proposal-only; human adjudication and production merge are not granted.

## Decisions

| Decision | Count |
| --- | ---: |
| `true_positive` | 30 |
| `false_positive` | 0 |
| `defer` | 0 |

Source-backed proposal precision is 30/30 = 1.0000. The Wilson 95% lower bound is 0.8865, so this calibration sample passes the configured proposal-precision thresholds of point estimate >= 0.95 and Wilson lower bound >= 0.80.

This is not a training-admission decision. `human_adjudication=not_granted`, `production_merge=not_granted`, and `training_rows=0` remain fixed.

## Source-Backed Findings

All accepted proposals use a complete literal-key parameter dictionary whose reaching definition is unique within the processing call's lexical scope. Reused variable names (`alg_params`, `param`, `par`, `params`, `parameters`, and `cmd_dict`) are replaced by complete assignments before the next call rather than partially or conditionally mutated. The recovered values expose at least one recorded upstream-output to downstream-input dependency per record.

No observed record triggered the rule's fail-closed conditions. The review explicitly checked for:

- dynamic dictionary keys;
- indexed, `.update`, or other partial mutations before `processing.run`;
- conditional or ambiguous reaching definitions;
- cross-scope dictionary propagation;
- dictionaries that were statically resolvable but irrelevant to the recorded multi-step dependency.

## Residual Risks

- The packet contains several near-duplicate workflow templates. The 30/30 result measures row-level proposal precision for this packet, not broad structural diversity.
- Several dependencies are materialized-file aliases rather than in-memory result objects. Their expressions are source-explicit and valid here, but future implementations must compare resolved value expressions conservatively.
- Passing this proposal calibration does not authorize rule deployment, corpus-wide recovery, validation/test eligibility, or training-row emission.

## Outputs

- `docs/reports/qgis_family_calibration_v2/parameter_dictionary_proposals_v1.jsonl`
- `docs/reports/qgis_family_calibration_v2/parameter_dictionary_proposals_v1_summary.json`
- `docs/reports/qgis_family_calibration_v2/parameter_dictionary_proposals_v1_summary.md`
