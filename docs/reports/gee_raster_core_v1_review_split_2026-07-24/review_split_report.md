# GEE Raster Core Review Split

Strict source/sequence-disjoint split and 50-row human review package for grafted GEE raster-core rows.
This remains a review sidecar and does not grant training, validation, or test admission.

## Summary

- Input rows: 11,454
- Eligible grafted rows: 11,397
- Excluded rows: 57
- Connected components: 8,494
- Unique sources: 11,397
- Unique L3 sequences: 8,494
- Review rows: 50
- Split counts: {'test': 1140, 'train': 9117, 'val': 1140}
- Review split counts: {'test': 5, 'train': 40, 'val': 5}

## Leakage Checks

- Source-disjoint verified: `True`
- Exact L3-sequence-disjoint verified: `True`

## Decision

- Training admission: `not_granted`
- Validation eligible: `False`
- Test eligible: `False`
- Next gate: human review of 50-row task text and core-chain fidelity
