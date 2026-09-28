# GEE P0 Data Authority Repair Design

## Objective

Make the retained GEE corpus usable as evidence-tiered raster and L3 supervision without presenting partial traces as complete workflow gold. The change repairs deterministic authority and auditing code only; it does not regenerate large datasets or start training.

## Decisions

1. Step8 must load the complete `l3` mapping from the selected versioned `id_mappings_v2.json`. It must not infer vocabulary from workflow samples. Unknown codes and malformed mappings stop the build with an actionable error.
2. Step7 may use full `script_id` metadata grafting. Legacy facts CSV lookup remains available, but duplicate simplified keys are accepted only when their metadata is identical. Conflicting duplicates stop the build instead of allowing last-write-wins behavior.
3. Description alignment is a deterministic evidence check, not an LLM reconstruction step. The first policy covers the confirmed export, chart, and visualization claim families. A mismatch marks the row partial; policy controls whether it is reported or quarantined.
4. Source-aware split grouping uses connected components over every available trusted identity plus the exact L3 sequence. This keeps both same-source and same-sequence rows together. Strict mode rejects rows without a trusted source identity; compatibility mode reports the gap and retains the legacy fallback.
5. Existing `outputs_v2` artifacts remain immutable during implementation. A later read-only audit quantifies migration impact before any regeneration decision.

## Data Contracts

Trusted source identity is read from explicit workflow metadata fields such as `source_hash`, `source_group`, `repository`, or `template_group`. Batch-like `script_id` prefixes are not trusted source authority.

Quality-gate annotations gain an alignment result and source identity status. Reports separately expose sequence leakage, source-group leakage, missing source identity, and description claim mismatches.

Step8 output provenance records the mapping and skip-list files actually used for cleaning. Upstream provenance is retained separately when it differs.

## Failure Behavior

- Invalid or incomplete L3 authority: stop Step8.
- Unknown L3 code: stop Step8 and name the code.
- Conflicting facts key: stop Step7 and name the key and source files.
- Missing source identity in strict split mode: stop candidate construction.
- Description mismatch: annotate in report mode; quarantine in strict mode.

## Verification

Use `unittest` because the active environment does not provide pytest. New tests must demonstrate red-green behavior for each contract. Run focused pipeline/quality-gate tests, compatibility tests, compilation, and `git diff --check` before completion.
