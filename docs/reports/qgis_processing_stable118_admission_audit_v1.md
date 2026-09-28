# QGIS Processing stable118 Admission Audit

## Verdict

`stable118` is a technically replayable proposal, but it is **not admitted** into
the delivered Processing training set. The current deliverable remains 177 rows.

The proposal's internal `taxonomy_admission=granted` flag is self-issued build
metadata, not a user-reviewed anti-bloat decision. It must not override the current
stable110 authority.

## Verified Results

- Authority tests and exporter tests: 3/3 passed after fixing the exporter import
  path to include `src`.
- Mapping replay: 3,163 rows; 53 route changes relative to stable110, including 12
  direct, 12 split, 4 recovery, 11 API-sidecar, and 14 partial-resolution rows.
- Increment exporter: 26 selected direct rows, 10 description-fidelity passes,
  7 canonical rows, and 3 duplicates.
- Current remote source replay: 7/7 SHA verified.
- Real V4 loader/loss/backward: 7/7 rows, finite loss/gradients, no checkpoint and
  no training.
- Cross-pool dedup against the verified 177-row package: 184 input, 184 canonical;
  the seven rows are net-new by source region, call graph, and exact training pair.

## Blocking Risks

- The eight new classes have normalized-body support `12, 5, 3, 2, 2, 1, 1, 1`;
  five classes therefore have support at most two. Freezing them only to increase
  row count would recreate taxonomy accretion without corpus-level evidence.
- The seven-row increment contains one 52-step chain with a 2,738-character task
  description. The production loader uses `max_text_length=128`, so most task
  semantics are truncated even though the 54-token target chain itself fits.
- The proposal yields only seven rows: 177 + 7 = 184. It does not satisfy its stated
  goal of moving the current Processing delivery beyond 200.

## Next Gate

Keep stable110 as the delivered authority. Before any stable118 promotion:

1. Remove or reconstruct the 52-step row as complete task-bounded subworkflows whose
   descriptions fit the model input without semantic loss.
2. Review low-support classes under an explicit anti-bloat policy; exact semantics
   alone do not justify a permanent class when corpus support is one or two.
3. Process the 16 newly unlocked recovery/split rows in batch under existing boundary,
   description, source replay, and four-layer dedup gates.
4. Promote only after the resulting verified increment reaches the 200-300 delivery
   stage without relaxing quality thresholds.
