# GEE Batch9 v8.8 AST/DAG A/B Replay

## Decision

Batch9 has completed its frozen v8.8 AST/DAG gate. The two independent runs are
byte-identical for the selection, parsed workflow DAGs, parse-failure sidecar, and
summary. This is a recovery-stage result only: no facts, task text, training rows,
or model-training artifacts were generated.

## Replay Evidence

- Population: 5,000 source-disjoint source contents: 4,000 `helper_export` and
  1,000 `control_flow_export`.
- Selection SHA256: `bd489a279fd904e6b7eccd37f9d6336e44a6de377156bfb35bf9ee0dce3aed80`.
- AST: 4,997 successes and 3 fail-closed parse failures. The failures remain
  recorded in the sidecar; they are not repaired or substituted.
- DAG source status: 187 `passed`, 140 `partial`, and 4,670 `fail_closed`.
- Byte-identical A/B business artifacts:
  - `workflow_dags.jsonl`: `73479cdd3b079f441fef7ea76e40a32d92fe06cee15ee98623afbe25ddcd7340`
  - `parse_failures.jsonl`: `03beb53ba1d2b71d9da9e27cd619bdf9e41f82468f226b5a767a3ae070bc72f0`
  - `summary.json`: `ea8a0bdf713b15658675894ace653946048deb5c076ee21b96f092a0c33d1110`
- Parser authority: `scripts/parse_gee_js_with_locations.js`, SHA256
  `d62681ba9e6861020ab8e9657e2083e97467b685af56a938404312760de97b57`.

The leading fail-closed workflow reasons are preserved as diagnostic counts, not
as relaxed admission criteria: unresolved dependency (6,903), callback core calls
without structural map (8,750), reused core-call source span (4,422), unresolved
call in dependency closure (812), control flow in dependency closure (278), and no
core calls (227).

## Locations And Next Gate

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch9_5000_v8_8_20260806/`.
The authoritative runs are `dag_v8_8_authority_a` and `dag_v8_8_authority_b`.

Next, run the unchanged v8.8 fidelity A/B replay using these DAG outputs. Only after
fidelity, typed mapping, facts, expansion, and the required sampled full-source
audit may a batch-level train-only admission be considered. Batch8 remains the
current 7,971-row semantic train-only authority.
