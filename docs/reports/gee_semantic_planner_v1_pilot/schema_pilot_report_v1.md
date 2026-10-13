# GEE Semantic Planner Data v1 — Schema Pilot

**Status: PILOT_ONLY / NOT_ADMITTED**

- Source rows scanned: `128447`
- Selected rows: `5`
- Maximum rows: `40`
- Source SHA-256: `09c37104d2fd33138cbc15d5d23676d4d169acf1d0cfb8057a0baf3a100c02a2`
- Reservoir seed: `20261008`
- Reservoir size per stratum: `50`
- Selection: deterministic Algorithm-R reservoir + maximal-marginal-gain selection
- G3 reconstruction: `not_performed`
- Training/inference: `not_run`
- Semantic gold: `false`

## Strata
- `ordinary_remote_sensing`: 5/5 (shortfall=0)
- `index_concept`: 5/5 (shortfall=0)
- `temporal_series`: 5/5 (shortfall=0)
- `classification_regression`: 5/5 (shortfall=0)
- `multi_source`: 5/5 (shortfall=0)
- `branch_or_parallel`: 5/5 (shortfall=0)
- `repetition_or_run_cap`: 5/5 (shortfall=0)
- `long_or_multi_output`: 5/5 (shortfall=0)

## Counterfactual discovery
- available: `0`
- undetermined: `4`
- unavailable: `2`

## Omission-collapse audit
- safe_omission: `0`
- high-impact_collision: `0`
- undetermined: `0`
- insufficient_pair_evidence: `12`

## Implementation invariance
- available: `0`
- undetermined: `0`
- unavailable: `1`

## Leakage audit
- records with leakage hits: `0`
- leakage hit types: `{}`

## Review status
- `pending`: `5`

## Link validation
- records checked: `5`
- validation errors: `0`

## Provenance / identity
- source_line_no recorded: `yes`
- source_script recorded: `yes`
- source_sha256 recorded per record: `yes`
- duplicate source_script: `blocked on detection`
- missing source_script: `blocked on detection`

## Governance
- `schema_status`: `pilot_only`
- `training_admission`: `not_granted`
- `production_samples`: `0`
- `semantic_gold`: `false`
- G0/G1/G2/G3 modification: `none`
- model loading/inference/training: `not_performed`
- RL/Blueprint-v3 freeze/scale-up: `not_performed`

## Stop

This is provisional schema-review evidence only. No training admission, G3 reconstruction, Blueprint-v3 freeze, RL, or scale-up is authorized.
