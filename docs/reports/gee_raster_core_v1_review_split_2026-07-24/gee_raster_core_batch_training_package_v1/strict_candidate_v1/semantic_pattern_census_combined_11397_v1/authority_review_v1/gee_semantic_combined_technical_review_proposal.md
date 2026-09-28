# GEE Semantic Census Combined Technical Review Proposal

Date: 2026-07-28

This report is a technical proposal. Human adjudication, training admission,
validation/test eligibility, and production merge remain not granted.

## Combined Census

- Source authorities in scope: 11,397
- Source SHA verified: 11,397/11,397
- AST/extractor successful: 11,391
- Source syntax failures: 6
- Signature proposals: 261 across 97 source SHA
- Semantic accepted after dependency closure: 154 across 39 source SHA
- Semantic fail-closed: 107
- Authority-pattern representatives: 43
- Training rows emitted: 0

The six parser failures are invalid source files, not an Acorn coverage gap:
two unterminated block comments, one missing comma, `NDVI mean`, `++1`, and an
invalid leading-zero floating literal. They stay source-level fail-closed.

## Pattern Support

| Pattern | Proposal rows | Proposal SHA | Accepted rows | Accepted SHA | Technical status |
|---|---:|---:|---:|---:|---|
| annual mean/clip | 227 | 95 | 128 | 39 | promotion candidate pending human review |
| year/polarization preprocess | 16 | 2 | 16 | 2 | insufficient independent support |
| polarization concat/select | 18 | 4 | 10 | 2 | insufficient independent support |

All 43 authority-pattern representatives were inspected as technical
proposals. Their direct canonical chains and source-backed dependencies are
complete. Misleading target names such as `S1_median` and `median` must not be
used to generate task text; the source operator is `mean`.

## Near-Duplicate Stress Test

Whitespace-normalized full-source similarity found four pairs at ratio >=0.80:

| Similarity | Source A | Source B |
|---:|---|---|
| 0.9750 | `script_4889` | `script_4894` |
| 0.9056 | `script_244591` | `script_244592` |
| 0.8865 | `script_22213` | `script_22207` |
| 0.8619 | `script_64651` | `script_113500` |

Collapsing all four pairs conservatively reduces annual mean/clip support from
39 source SHA to 35 template clusters. If human review confirms 35/35, the
Wilson 95% lower bound is 0.901, above the required 0.80; observed precision is
1.0, above the required 0.95. This stress test does not itself grant human
approval.

The two preprocess/concat authorities are the high-similarity
`script_244591/244592` pair. They provide only one conservative template family,
so those patterns remain proposal-only regardless of row count.

## Decision Proposal

1. Human-review the 35 conservative annual mean/clip template clusters using
   the combined representative CSV. Promotion requires precision >=0.95 and
   Wilson 95% lower >=0.80.
2. If the gate passes, export at most one annual mean/clip row per source
   authority/template cluster before task-text generation. Do not export all
   128 accepted rows.
3. Keep preprocess and concat/select fail-closed for batch promotion until new
   independent source families are found.
4. Generate later task text only from canonical operators, semantic facts, and
   accepted dependencies; never from target-variable names or old script task
   descriptions.
