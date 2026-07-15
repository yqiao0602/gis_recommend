# QGIS Core Signature Review

Each row represents an operator implementation signature, not a workflow.
Review the trace evidence and bounded catalog candidates. An automatic proposal
is only a review aid and is not accepted until `review_status=reviewed` and
`human_decision=accept` are recorded. Ambiguous or unsupported rows must remain
unresolved. No row in this package is admitted to training.

Confirmed decisions are appended to `adjudication_decisions.jsonl` and checked
against this immutable workbook with
`scripts/validate_qgis_core_signature_adjudications.py`. Accepted decisions are
operator-anchor candidates only; they are not workflow or training rows.
