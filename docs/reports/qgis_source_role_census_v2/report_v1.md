# QGIS Source-Role Census v1

Date: 2026-08-11

This is a read-only structural census over 47,852 source authorities. It does
not call an LLM, map L3, emit training rows, or modify authority. The server
ledger is `source_role_census_v1.jsonl`; local copies retain only the summary
and hash ledger.

## Primary Roles

| pool | user_workflow | processing_implementation | api_semantic_operation | api_plumbing | unclassified | missing |
|---|---:|---:|---:|---:|---:|---:|
| Processing (8,466) | 2,068 | 1,011 | 1,361 | 2,139 | 1,592 | 295 |
| API (39,386) | 141 | 1 | 7,667 | 9,516 | 22,046 | 15 |
| Total | 2,209 | 1,012 | 9,028 | 11,655 | 23,638 | 310 |

The Processing pool contains API-shaped sources as well; the role is assigned
from source structure rather than the manifest pool label. This is intentional:
it exposes Processing authority rows that are actually API implementation or
plumbing code.

## Signals

Among Processing `user_workflow` rows, 1,689 contain task-semantic terms,
1,851 contain input/output markers, and 183 show a recoverable downstream data
dependency under the current lightweight AST heuristic. Among
`processing_implementation` rows, the corresponding dependency count is 116.
API semantic rows with task and input/output signals number 3,474 in the API
pool. These are census signals, not admission decisions.

Applying a deliberately strict preliminary screen
(`processing_run_count >= 2`, task/input-output evidence, and a dependency)
leaves 169 Processing `user_workflow` candidates and 114
`processing_implementation` candidates. They still require task-boundary,
fidelity, L3 mapping, description, deduplication, and V4 gates.

## Interpretation

The corpus is not 47,852 equivalent workflow samples. The largest population is
unclassified source (23,638), followed by API plumbing (11,655) and API
semantic operations (9,028). The main training supply should therefore start
with source-role and workflow-value gates, not with an unrestricted LLM replay.
API semantic operations should primarily populate the API semantic catalog and
L2/L3 implementation knowledge; API plumbing remains evidence and should not
enter the main workflow corpus.

The first source-integrity run incorrectly hashed decoded text and reported
6,606 false mismatches. v2 hashes raw source bytes before UTF-8 decoding; the
final 310 missing rows match the known server-side structural absence. No
training rows were emitted.
