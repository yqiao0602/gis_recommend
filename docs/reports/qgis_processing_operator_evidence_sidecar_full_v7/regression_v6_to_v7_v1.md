# Processing operator evidence sidecar v7 — provable name binding

Candidate-only evidence layer. No L3 mapping, training row, authority, evaluation
split, or checkpoint was produced or modified.

Same frozen input as v6: `qgis_asset_normalized_v1.jsonl`,
SHA256 `45a1c12d3d79cbdbee6b75f4fa80b10fad1dd8617faf6e378c61203c1c3ffe59`.
Only the extractor rule changed, so every delta below is attributable to the rule.

## Defect repaired

v6 resolved a parameter dictionary passed by name with a module-wide
`ast.walk()` collection of `{name: last assignment seen}`. That construction
cannot establish any of the properties the label `name_to_static_assignment`
claims: it ignores scope, ignores statement order, ignores dominance, and ignores
mutation. It silently attributed a *different* call's payload to the call under
inspection whenever a name was assigned more than once.

v7 replaces it with rule `dominating_same_scope_static_dict_v2`. A binding is
accepted only when all of the following hold, and each is recorded:

1. Exactly one assignment to the name structurally dominates the call — it lies on
   the call's own block path, strictly before the statement that leads to the call.
   Conditional branches that do not contain the call therefore never qualify.
2. That assignment is in the same lexical scope as the call. Enclosing-scope
   assignments captured by a closure are rejected, since the call time is unprovable.
3. No rebinding or mutation of the name occurs between the assignment line and the
   call span. The guard covers `=`, augmented and annotated assignment, `del`,
   `for`/`with` targets, walrus, subscript writes such as `params['X'] = ...`, and
   `update` / `setdefault` / `pop` / `popitem` / `clear` calls.
4. The bound value is a static dict literal.

`except` and `match case` clauses are not statement fields, so their bodies were
invisible to the path index and every call inside them failed closed. They are now
traversed as statement containers, while keeping the correct dominance result that
a `try`-body assignment does not dominate a call in the handler.

Accepted recoveries carry `binding_provenance`: `name`, `rule`,
`assignment_lineno`, `assignment_span`, `assignment_scope`, `call_scope`,
`assignment_scope_verified`, `dominance_verified`, `mutation_guard`,
`dominating_assignment_lines`, `interfering_write_lines`. A recovered binding is
therefore replayable and is never presented as a source-level literal call.

## Result

| Measure | v6 | v7 |
|---|---:|---:|
| Source SHA verified | 591/591 | 591/591 |
| AST call recovery | 591/591 | 591/591 |
| `verified_static_dict` | 508 | **511** |
| `verified_positional_arguments` | 68 | 68 |
| `deferred` | 15 | **12** |
| Static INPUT/OUTPUT-key calls | 435 | **438** |
| I/O evidence calls (incl. positional) | 501 | **504** |
| Provider-prefix evidence calls | 589 | 589 |
| Accepted name bindings | 229 (unproven) | **224 (proven)** |
| Training rows | 0 | 0 |

Parameter completeness, reported for the first time:
`static_parameter_complete=50`, `static_parameter_partial=529`,
`parameter_unresolved=12`. Complete means every key is a literal and every value is
a literal; partial means the payload structure is static but at least one key or
value is a runtime expression. The 50/591 complete figure is the honest ceiling for
parameter-level facts in this pool.

Provenance completeness over the 224 accepted bindings: `assignment_lineno` 224/224,
`assignment_scope_verified` 224/224, `dominance_verified` 224/224,
`mutation_guard_verified` 224/224, `assignment_span` 224/224.

Remaining defer reasons: `interfering_write_before_call` 5,
`no_dominating_assignment` 5, `parameter_expression_not_static_dict` 2.

## Regression cohorts

Row-level transitions across the 591 rows: 6 `deferred → verified_static_dict`,
3 `verified_static_dict → deferred`, 4 corrected key sets with unchanged status.
No other row changed.

False positives eliminated — `qgis:joinattributesbylocation`, 4 rows
(`08d27214…`, `39a4066f…`, `8f232f9c…`, `f76b25be…`). v6 recorded
`… PREDICATE, SUMMARIES` copied from a later assignment belonging to a different
algorithm. v7 records the dominating assignment's
`… METHOD, PREDICATE, PREFIX` with `assignment_lineno` 42/42/35/35 and
`mutation_guard=no_interfering_write`. `SUMMARIES` leakage 4 → 0.

False negatives recovered — 6 rows where a static dict does dominate the call but a
later unrelated assignment had shadowed it: `qgis:filedownloader` ×3
(`URL, OUTPUT`, assignment lines 713/712/706) and `qgis:intersection` ×3
(`INPUT, OVERLAY, OUTPUT, INTERSECTION`, assignment lines 336/339/337).

Newly deferred — 3 rows that v6 reported as verified while a write intervened
between the assignment and the call: `native:rastercalc` (assignment 67, write 73,
call 75), `qgis:rastersampling` (assignment 193, writes 194–195, call 196),
`gdal:hillshade` (assignment 15, writes 27–28, call 30). These are correct
fail-closed outcomes, not lost recall.

## Scope limits

- The operator ID itself is still required to be a source literal. All 591 rows are
  `literal_source_evidence` with exactly one call each. Statically resolvable dynamic
  forms such as `alg_string = "grass7:r.reclass"; processing.run(alg_string, …)` are
  not in this pool; they belong to the separate 496-row dynamic candidate pool.
- Provider evidence remains the operator-ID prefix only. It is not a provider
  version, availability, or I/O contract proof.
- `deferred=0` in the v6 summary referred to row status. Call-level parameter
  evidence was never 591/591 and is not now: the ceiling is 511 + 68.

## Verification

- Focused tests: 15/15 (`tests/test_build_qgis_processing_operator_evidence_sidecar.py`),
  covering dominance, cross-scope closure rejection, subscript and `update` mutation
  guards, non-dominating conditional assignment, except-handler indexing,
  try-to-handler non-dominance, completeness tiers, and non-literal dict keys.
- `compileall` clean; `git diff --check` clean.
- Local mirror re-hashed after transfer; all three artifact digests match
  `hash_ledger_v1.json`.

## Server note

`/` and `/data` on the compute server are both at 100% capacity (0 bytes and
~1 MB free), so the run wrote to `/tmp` (tmpfs) and the full ledger was copied back
here rather than left server-side. Nothing was deleted. The v6 directory is
untouched and remains the superseded reference.
