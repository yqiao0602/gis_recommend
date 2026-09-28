# QGIS Full-Pool Routing Baseline v1

This report is the first unified routing rollup over the historical **47,852-source**
QGIS census. It uses the frozen source-role and workflow-value summaries; it is
not a new source replay and it does not grant training admission.

**Status:** the true full-pool candidate-recall experiment is not yet run. A source-level
candidate ledger is required before recall can be computed. The numbers below
are the denominator-defined routing baseline and the observed curated yield,
not a claim that all 47,852 sources were replayed through one extractor.

## Recall funnel

| Stage | Count | Share of 47,852 | Meaning |
| --- | ---: | ---: | --- |
| Source census | 47,852 | 100.000% | Processing + API source authorities |
| `user_workflow` role | 2,209 | 4.617% | Structural role signal, not training |
| Processing tier-1 multi-step | 169 | 0.353% | Strict multi-step workflow screen |
| Processing tier-2 single-step | 286 | 0.598% | Single-step Processing screen |
| Processing first queue | 455 | 0.951% | Tier-1 + Processing tier-2; candidate input to replay |
| Processing tier-3 implementation | 983 | 2.055% | Implementation candidates; separate lane |
| API semantic candidate | 4,737 | 9.899% | Operator-semantic knowledge candidates |
| Unclassified deferred | 29,673 | 62.024% | No accepted cheap structural signature yet |
| Curated train-only observed | 28 | 0.058% | Gold/Silver rows after review and dedup; not full-pool recall |

The 455-row Processing queue was replayed in a bounded workflow pilot. It
produced 70 structural candidates, 69 description-fidelity passes, and 21
pre-review Silver candidates; independent review retained 19 rows (15 Gold,
4 Silver). A separate seed-subworkflow route added 9 reviewed rows, producing
28 curated rows in total. The 28 rows therefore represent an observed yield
from selected/replayed lanes, not an exhaustive 47,852-source candidate recall.

## What this experiment establishes

The first full-pool routing baseline is now explicit: the current cheap screen
routes 455 Processing rows, 983 implementation rows, and 4,737 API semantic
rows into different production lanes, while 29,673 rows remain deferred. It
also establishes the current end-to-end observed yield of 28 curated rows, but
does not claim that all 47,852 rows passed the same downstream gates.

The next production experiment must select one denominator-defined lane (for
example, all 983 tier-3 Processing implementations or a bounded deterministic
API family), emit source-level candidate rows, and measure candidate recall,
dedup retention, and Gold/Silver yield on that lane. Only then can a true
lane-specific production rate be compared with this baseline.

## First execution result (Processing-only)

The current deterministic replay processed the full 8,466-row Processing pool.
The 39,386-row API authority was not replayed by this command. Processing
produced 100 `auto_accept_candidate` rows. This is not a sampled 100-row subset;
the remaining Processing rows were routed to mapping defer, call-graph
recovery, API sidecar review, or exclusion. All 100 source hashes were present
in the 47,852-source authority union:

```text
8,466 Processing sources -> 100 direct structural candidates
direct candidate rate within Processing = 100 / 8,466 = 1.1812%
100 / 47,852 = 0.2090% is only a cross-pool coverage ratio, not full-pool recall
```

This is a Processing-only direct-candidate result, not full-pool candidate
recall and not a Gold/Silver acceptance result. The 100 rows have not undergone a shared
semantic review in this execution. The previously curated 28 rows are reported
separately as an observed historical yield (`28 / 47,852 = 0.0585%`) with no
candidate-stage linkage claim. Execution artifact:
`first_recall_execution_v1.json`.

The replay-lane decomposition is recorded in
`processing_replay_yield_v1.json`. Of the 8,466 Processing rows, 222 recovery
rows and 203 API-sidecar rows already carry mapped L3 chains and operator/call
site evidence, but remain structurally deferred or blocked; they are the first
bounded expansion targets. A further 346 mapping-deferred rows have mapped L3
chains but unresolved structure. The remaining 7,567 rows require more basic
operator/boundary recovery and should not be sent directly to semantic review.

## Authority and limitations

- Source-role and tier summaries are read-only census artifacts.
- No authority, validation/test split, benchmark, or production profile changed.
- Historical package counts (508/539/293) are excluded from the 47,852 funnel.
- The 28 curated rows are not extrapolated to the deferred population.
