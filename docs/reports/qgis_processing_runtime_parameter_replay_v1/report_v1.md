# QGIS Processing runtime-parameter description replay v1

Date: 2026-08-01

## Decision

Admit six source-replayed, deterministic-description Processing rows as an
isolated train-only increment. This raises cumulative Processing admission from
168 to 174 rows. Validation, test, production merge, LLM generation, and model
training remain disabled.

## Batch Method

- Start from all 73 previously description-deferred direct rows.
- Recover a dynamic value only when AST provenance proves that it comes from a
  workflow input (`parameters[...]`) or a dominating same-scope
  `self.parameterAs*()` assignment.
- Describe the value as supplied by the workflow input; do not invent a literal.
- Keep bare locals, computed expressions, non-dominating branches, dictionary
  mutation, and unresolved references fail-closed.
- Replay the complete direct pool, then apply source replay and four-layer plus
  cross-pool deduplication before export.

## Results

| Gate | Result |
| --- | ---: |
| Direct pool | 150 |
| Description fidelity passed | 97 (previously 77) |
| Newly recovered description rows | 20 |
| Still description-deferred | 53 |
| Source missing | 1 |
| Exact training-pair duplicates | 13 |
| Canonical source-replay candidates | 6 |
| Source SHA / AST / call-span verified | 6 / 6 |
| Train-only exported | 6 |
| Real V4 loader/loss/backward | 6 / 6 |

The longest admitted row has 52 Processing operators and 54 model tokens after
START/END are included. This is below the V4 limit of 100, so the workflow target
is not truncated. The smoke run loaded all six rows in one `[6, 100]` batch;
weighted loss and gradients were finite and no checkpoint was written.

## Evidence

- Source replay: `source_replay_v1/`
- Train-only package and smoke: `train_only_v1/`
- Dedup authority: `increment_audit_v2/`
- Full direct replay: `direct_description_candidates_v1.jsonl`
- Source replay JSONL SHA256:
  `2e19c29a07f609c15fb8e57c97a124f72582186b5c26cc34398463ab40770b07`
- Train-only JSONL SHA256:
  `618a75bb9409dcb2814298ab711b4eed00d1720e886bdfd1e42a2997bed13545`
- Smoke summary SHA256:
  `86cd1a4911dfd5980bbda5f5d43166052f4bec7ee9e3a1ffceb086bde1c242e5`

`direct_descriptions_v5/` and `increment_audit_v1/` are non-authoritative
diagnostics: the former loaded an obsolete staging module and the latter joined
the obsolete 107-row authority. Current authority is `direct_descriptions_v5b/`
plus `increment_audit_v2/`.

## Next Gate

Cluster the remaining 53 description-deferred rows by provenance failure and
calibrate only reusable, source-provable propagation rules. A rule is replayed
across the frozen pool once; rows still lacking exact provenance remain deferred.
The Processing target is 200 rows, leaving 26 rows.
