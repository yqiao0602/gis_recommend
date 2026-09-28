# QGIS `runalg` Isolated Adapter Calibration v1

Date: 2026-08-16

## Contract

This experiment evaluated an isolated structural adapter for legacy positional
`processing.runalg`. It does not modify the production extractor and does not
recover positional parameter names, I/O contracts, L3 labels, descriptions, or
training rows. It only rewrites AST-confirmed literal `runalg` call tokens to
same-width `run` tokens at the original source location, then validates the
resulting call order and data-dependency edges against an independent AST
audit.

The input packet is the frozen 30 calibration + 30 source/body-disjoint
holdout package in `../qgis_runalg_entrypoint_census_v1/`.

## Calibration

| Gate | Result |
|---|---:|
| Adapter exact literal call alignment | 30 / 30 |
| Recovered dependency-edge sources | 10 / 30 |
| Recovered dependency edges | 38 |
| Independent AST structural audit | 30 / 30 |

The independent audit verifies direct variable references plus only these
same-scope, non-transforming aliases: result dictionary lookup,
`QgsRasterLayer`, `QgsVectorLayer`, and `processing.getObject`. It also uses
the latest preceding definition on variable rebinding. Any other call,
cross-scope lookup, or unproved alias remains rejected.

## Source-Disjoint Holdout

| Gate | Result |
|---|---:|
| Adapter exact literal call alignment | 27 / 30 |
| Independent AST structural match | 26 / 30 |
| Accepted dependency-edge sources | 12 / 30 |
| Accepted dependency edges | 54 |

The four retained failures are structural coverage failures, not training
examples:

1. Three sources mix selected literal calls with additional dynamic `runalg`
   calls. The adapter refuses to rewrite unselected dynamic calls, so the
   frozen selected-call set cannot be aligned exactly.
2. One source has a positional static-output-path dependency. The adapter
   reports the edge, but the independent audit deliberately has no equivalent
   output-path proof rule.

Two earlier apparent audit failures were only edge-order representation
differences and are normalized as equal sets in the final audit. They are not
counted as failures.

## Decision

**Do not promote `runalg` to the production extractor.** The planned zero-error
source-disjoint holdout gate failed (26/30). The 26 structurally matching rows
remain candidate-only and cannot enter L3 mapping, description, Gold/Silver,
authority, validation/test, benchmark, model training, or checkpoint output
through this family result.

The bounded next option is a newly frozen, previously unused strict profile:
literal-only source calls with no dynamic sibling and no positional static
output-path dependency, followed by a fresh calibration/holdout. The current
holdout must not be reused to claim that a rule learned from its failures
generalizes. This report makes no decision to start that follow-up.

## Verification

Local verification: Ruff, `py_compile`, and pytest passed for the census,
adapter, and independent-audit scripts (9 tests total). Server sources under
`/home/yll` were read-only; server products were written under
`/home/qy/system_redesign` and copied back. Training rows emitted: 0.
