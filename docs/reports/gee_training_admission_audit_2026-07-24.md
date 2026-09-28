# GEE Training Admission Audit

This is a read-only audit for using existing GEE rows as unified L3 workflow training data.
It does not grant training admission and does not regenerate data.

## Summary

- Candidate workflows: 76,884
- Quarantined workflows: 30,515
- Gold rows: 0
- Silver-A rows: 14,362
- Silver-B rows: 58,402
- Rejected rows: 34,635
- Candidate unknown/empty text: 17
- Candidate description-chain issues: 61,084
- Candidate authoritative source identity: 0
- Active candidate L3 codes: 47
- Candidate Top10 L3 share: 74.94%
- Duplicate L3-sequence candidate items: 43,501

## Training Decision

- Training admission: `not_granted`
- Large dataset overwrite authorized: `False`
- Recommended next gate: review this audit, then build a bounded GEE_raster_core_v1 from gold/silver_a rows only

## Tier Definitions

- `gold`: usable text, valid schema/L3 chain, no description-chain issue, authoritative source identity.
- `silver_a`: usable text, valid schema/L3 chain, no description-chain issue, but missing authoritative source identity.
- `silver_b`: usable text and valid schema/L3 chain, but has description-chain or low-confidence risk.
- `rejected`: unknown/empty text, invalid schema/L3/length, or quality-gate quarantine.

## Top L3 Codes

- `L3_03_01_04`: 87,072
- `L3_03_09_05`: 77,726
- `L3_03_09_01`: 69,670
- `L3_03_09_06`: 49,235
- `L3_03_03_A`: 48,906
- `L3_03_01_01`: 42,966
- `L3_03_10_R`: 32,653
- `L3_03_03_L`: 32,166
- `L3_10_02_03`: 29,585
- `L3_03_01_05`: 22,591
- `L3_08_03_01`: 19,860
- `L3_01_02_03`: 17,504
- `L3_03_02_01`: 15,322
- `L3_10_04_01`: 15,201
- `L3_08_04_01`: 13,526
- `L3_01_03_04`: 13,310
- `L3_08_01_01`: 12,949
- `L3_03_07_01`: 8,410
- `L3_03_08_01`: 7,442
- `L3_01_13_01`: 6,823
