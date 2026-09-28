# GEE Raster Core Source Identity Graft

This sidecar attempts to graft replay-manifest source hashes onto the bounded GEE raster-core proposal.
It does not grant training, validation, or test admission.

## Summary

- Selected rows: 11,454
- Manifest files: 31
- Manifest keys: 237,811
- Grafted rows: 11,397
- Unmatched rows: 57
- Conflict rows: 0
- Invalid rows: 0
- Unique source hashes: 11,397

## Unmatched By Batch

- `Workflowoutput1-5000`: 33
- `Workflowoutput30000`: 2
- `Workflowoutput5000-10000`: 22

## Decision

- Training admission: `not_granted`
- Validation eligible: `False`
- Test eligible: `False`
- Promotion gate: human text/chain review and source-disjoint split rebuild required before validation/test use
