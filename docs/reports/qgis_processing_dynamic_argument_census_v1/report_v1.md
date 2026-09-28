# Processing Dynamic-Argument Census v1

## Population and method

The server read the 8,466-row Processing authority manifest in read-only mode.
Each readable source was SHA256-verified against the manifest and parsed with
Python AST. The census counts only direct `processing.run`, `runalg`, and
`runAndLoadResults` calls whose first argument is the requested algorithm ID.
Bare `run(...)` calls are reported separately and do not affect the Processing
module result.

## Result

| Source outcome | Count |
| --- | ---: |
| SHA-verified and parsed | 8,143 |
| Missing on server | 295 |
| Unparseable | 28 |
| Processing-module calls, literal IDs only | 2,818 sources |
| At least one nonliteral Processing-module ID | 484 sources |
| No direct Processing-module call | 4,841 sources |

The 484-source nonliteral subset represents 5.95% of the readable authority
population and contains 1,379 calls: 1,190 `Name` references, 32 attributes,
30 nested calls, 10 conditional expressions, 38 string expressions, 9
f-strings, 4 subscripts, 2 dictionaries, and 64 calls without a first argument.

## Consequence for the LLM route

The current `deferred_operator=387` ledger population is not the dynamic-ID
population: it already contains literal provider/algorithm IDs that are absent
from the current catalog or mapping authority. An LLM cannot turn a missing
catalog entry into a verified train label.

Processing must therefore use three separate lanes:

1. `Name` references: first apply expanded static assignment/caller/config
   recovery. Many can be deterministically resolved without an LLM.
2. Expression forms (attribute/call/conditional/string/f-string/subscript):
   use the LLM only to propose catalog-constrained candidates and line evidence;
   independent verification is still required before downstream admission.
3. No direct call, missing first argument, third-party provider/catalog miss:
   keep deferred or route to helper/wrapper/catalog work. They are not valid
   LLM training-label inputs.

The API corpus is deliberately out of scope for this report. No LLM call,
L3 assignment, description generation, training export, or authority merge was
performed.
