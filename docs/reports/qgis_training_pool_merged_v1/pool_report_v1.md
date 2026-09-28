# Official merged QGIS training pool v1: 629 rows

The merged admission the user ordered: audited existing 506 + 120 API-pattern
candidates + 3 standalone candidates, with all dedup layers **re-applied jointly**
across the three sources (sample identity, source-SHA + span overlap, exact
L3-sequence + task-text twins) rather than trusting the prior stages'
arithmetic.

## Result: 629 admitted, 0 cross-pool rejects

The three stages' prior cross-dedup held exactly: the 508-pool audit had already
removed the 2 twins, the pattern consumption had already removed its 10 pool
hits and 8 internal duplicates, and the standalone 3 (never previously
cross-checked) also pass cleanly here. No new duplicates surfaced at merge time.

| 指标 | 结果 |
|---|---:|
| Existing audited | 506 |
| New pattern candidates | 120 |
| Standalone candidates | 3 |
| Cross-pool duplicates at merge | 0 |
| **Final admitted** | **629** |
| 单步 workflow | 367 |
| **多步 workflow** | **262** |
| unique L3 sequences (whole pool) | 277 |
| unique task texts | 617 |
| Length 1 | 367 |
| Length 2–3 | 138 |
| Length 4–7 | 89 |
| Length 8+ | 35 |

**Unique multi-step L3 sequences: 227 of 262** (107 from the audited existing
pool, 120 from the pattern lane — the pattern lane's entire contribution is
sequence-unique). Largest multi-step group is 15 rows of
`Add Field → Calculate Field` (a known family), then 3-row groups; no dominant
duplicate structure.

Weights: 1.0 × 172 (52 audited GOLD + 120 pattern), 0.8 × 24, 0.7 × 430,
0.6 × 3.

## V4 smoke over the full pool

Real `TaskConditionedL3DatasetV4` + real `bert-base-uncased`, 20 batches:
dataset size 629, max content length 55 (budget 100), all losses finite
(sum 96.82), all gradients finite. No checkpoint written, no training epoch run.

## Standing

```text
QGIS raw assets            47,852
API pattern instances       4,880 → 875 unique chains → 120 candidates
Standalone semantic units   3,209 → 1,058 candidates → 3 candidates
Existing pool               508 → audited 506 valid (52 GOLD / 454 SILVER / 2 REJECT)
─────────────────────────────────
Official QGIS training pool 629  (admitted_train_only_candidate_v1)
   ├── single-step 367   (operator semantic supervision)
   └── multi-step  262   (workflow composition supervision, +84.5% over the old 142)
```

The 629 rows are `admitted_train_only_candidate_v1` — a versioned, hash-bound
pool, not yet a training run. `validation_eligible=false`, `test_eligible=false`,
`production_merge=not_granted` on every row. Consuming it in a training
experiment (e.g. the stable124-style baseline vs +629 comparison) is the next
user decision, and the GEE distribution analysis comes after that.
