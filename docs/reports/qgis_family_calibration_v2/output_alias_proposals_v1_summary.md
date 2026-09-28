# Output Alias Proposal Calibration v1

- Rule: 'propagate-single-scope-output-alias-v1'
- Source records reviewed: 30 (family=output_alias)
- Decisions: true_positive=21, false_positive=9, defer=0
- Proposal precision: 0.700 (21/30)
- Wilson 95% lower bound: 0.5212 (canonical evaluator calculation)
- Remote source verification: 30/30 SHA-256 matches; 0 mismatches; 0 unreadable sources
- Status: proposal_only=true; human_adjudication=not_granted; training_rows=0; training_row_emitted=false

## Failure modes

1. Nested outputs[Name][OUTPUT] reads are result-dictionary chaining, not a single result[OUTPUT] alias.
2. Conditional or repeated writes to an existing variable make the reaching alias ambiguous.
3. Helpers accepting dynamic output keys violate the literal output-key requirement.

No source files, core rules, or review_60_v1 records were modified.
