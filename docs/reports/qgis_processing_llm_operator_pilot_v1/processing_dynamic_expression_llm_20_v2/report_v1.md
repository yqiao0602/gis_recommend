# Processing Dynamic-Expression LLM Pilot v1

## Input

The pilot staged 50 source-SHA-verified Processing scripts from the full
dynamic-expression population: 25 calibration sources and 25 holdout sources,
with no source-SHA overlap. They contain 74 expression-form first arguments to
`processing.run` across 67 relevant scopes. Six oversized scopes were not
truncated or sent.

## Results

The bounded primary run attempted 20 eligible scopes:

| Outcome | Count |
| --- | ---: |
| Valid model responses | 15 |
| Unparseable model responses | 5 |
| Scope too large, not sent | 6 |
| Outside global request budget | 40 |
| Per-source request budget | 1 |
| New dynamic operator candidates | 0 |
| Training rows | 0 |

The 15 valid responses returned six catalog IDs, but all six were already
locally proved literal calls elsewhere in the same submitted scope. Therefore
they are not recovery of the dynamic expression and produce no
`unverified_candidate` or verified new operator.

After expanding local JSON parsing, five source retries (six scopes) produced
two valid abstentions and four further unparseable responses. The retry added
no candidate.

## Diagnosis

The sampled expressions separate into deterministic and irrecoverable forms:

- conditional literals such as
  `gdal:warpreproject if is_raster else native:reprojectlayer`;
- wrapper calls carrying a literal ID such as
  `matchAlgo('native:deletecolumn')`;
- provider/custom-tool concatenation such as `grass7:` plus an unknown name,
  or a third-party provider identifier;
- actual request/config access such as `request.args['alg']`.

The first two require additional deterministic AST recovery, not an LLM. The
third needs catalog/provider authority and remains deferred. The final form
requires runtime evidence. The LLM provided no evidence-bearing new catalog
candidate for any of these forms in this pilot.

## Decision

Do not expand this LLM dynamic-expression route to the 125-call population.
Keep it isolated with zero training admission. The next Processing action is a
deterministic recovery pass for conditional literal IDs and literal-bearing
wrappers, followed by the existing boundary/L3/description/dedup gates. API is
out of scope.
