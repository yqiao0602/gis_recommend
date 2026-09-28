# GEE Pipeline P0-C Auxiliary Context Design

## Goal

Stop Step2 and Step8 from deleting real Earth Engine operations merely because their names begin with `ee.Number`, `ee.Date`, or `ee.List`, while retaining the intentional removal of standalone value constructors.

## Confirmed defect

Step2 uses prefix matching against auxiliary names. Step8 classifies the second dotted segment as auxiliary. Both rules therefore remove method calls such as `ee.Number.add`, `ee.Date.advance`, and `ee.List.sequence` together with standalone constructors such as `ee.Number`.

## Decision

Use a shared, closed set of exact auxiliary constructor names. A call is auxiliary only when the normalized operator string exactly equals one of those constructors. A longer Earth Engine path is an operation and remains in the workflow. This is deterministic from the existing operation evidence and does not require receiver-type guessing.

The shared set is deliberately limited to `ee.Number`, `ee.Date`, and `ee.List`. Step2 and Step8 have historical disagreements for other constructor categories, especially geometries; changing them is outside P0-C. The policy does not classify native JavaScript calls; Extractor P0-B owns that boundary. Unknown receivers remain unchanged.

## Alternatives rejected

1. Keep prefix matching and add exceptions for known methods. This would require an incomplete, growing method catalog and would continue to fail on unseen valid methods.
2. Infer receiver types from the flattened operation string. The legacy Step2/Step8 inputs do not retain enough AST binding context for reliable inference.
3. Stop all auxiliary filtering. This would change the historical core-chain policy more broadly than P0-C requires.

## Implementation

- Add a small shared policy module containing the exact three-constructor allowlist and `is_auxiliary_value_constructor()`.
- Make legacy Step2 and Step8 delegate only their `ee.Number`/`ee.Date`/`ee.List` decision to that policy, preserving their other historical categories.
- Keep all length, cycle, deduplication, taxonomy, provenance, and training-admission behavior unchanged.

## Verification

- RED tests must show current Step2 and Step8 delete `ee.Number.add`, `ee.Date.advance`, and `ee.List.sequence`.
- GREEN tests must show exact constructors are removed while longer GEE method paths and native/unknown receivers remain.
- Run focused legacy/P0/provenance tests, compileall, and scoped diff checks.
- Do not regenerate `outputs/` or `outputs_v2`, call an LLM, or train a model.
