# GEE Raster Core V1 Proposal

Bounded proposal derived from the audited GEE candidate pool.
It is train-only and does not grant validation/test admission.

## Summary

- Candidate rows: 76,884
- Quarantined rows: 30,515
- Train rows: 61,495
- Held-out rows: 15,389
- Selected rows: 11,454
- Train silver-A rows: 11,454
- Train silver-A core rows: 11,454
- Train non-silver-A rows: 50,041
- Train silver-A non-core rows: 0

## Policy

- Selection tier: `silver_a`
- Selection scope: `core_analysis`
- Train only: `True`
- Validation eligible: `False`
- Test eligible: `False`
- Sample weight: `0.5`
- Source identity gate: authoritative_identity_required_before_validation_or_test

## Selection

- Selected by tier: {'silver_a': 11454}
- Selected by scope: {'core_analysis': 11454}

## Decision

- Training admission: `not_granted`
- Recommended next gate: graft replay-manifest source_hash and source identity before any validation/test promotion

## Example Script IDs

- `Workflowoutput1-5000_script_4364`
- `Workflowoutput1-5000_script_1237`
- `Workflowoutput1-5000_script_2252`
- `Workflowoutput1-5000_script_4914`
- `Workflowoutput1-5000_script_1469`
- `Workflowoutput1-5000_script_4970`
- `Workflowoutput1-5000_script_4202`
- `Workflowoutput1-5000_script_1852`
- `Workflowoutput1-5000_script_4913`
- `Workflowoutput1-5000_script_4672`
