# QGIS Seed Subworkflow Candidate Intake v1

## Result

- Reviewed Processing seed rows: 19
- Multistep reviewed seed rows: 6
- Single-step seeds excluded: 13
- Derived review candidates: 31
- Parent semantic decisions among candidates: Gold=11, retained Silver=20
- Candidate path lengths: 2 steps=18, 3 steps=9, 4 steps=4
- Training rows emitted: 0

## Construction Contract

Each candidate is a directed contiguous path already present in one reviewed
Processing source workflow. The path may start at an internal DAG node, but it
cannot combine operators from different seeds. Every adjacent pair passes the
official QGIS catalog input/output compatibility test. Candidate records retain
the parent sample ID, parent source SHA256, exact path indices, L3 sequence,
and the `qgis_catalog_io_contiguous_source_path_v1` constraint profile.

## Admission Status

All 31 rows are `pending_independent_semantic_review` and
`not_granted_candidate_only`. The generated task text is a review label, not a
claim that the subpath is an independently meaningful user task. In particular,
paths made mostly of repeated selection-saving operations are expected to be
rejected. This package does not modify authority, validation, test, benchmark,
or checkpoints.

## Next Gate

Review the 31 rows against their parent source semantics. Retain only paths
whose local goal remains intelligible after removing the surrounding workflow;
classify them as `independent_workflow`, `implementation_subworkflow`, or
`duplicate_or_parent_contained`. Only the first class may proceed to a separate
Gold/Silver review. The packet is at `semantic_review_packet_v1/`; every
descendant is permanently grouped by its parent source SHA in future splits.
Do not use catalog I/O compatibility as a substitute for task semantics.
