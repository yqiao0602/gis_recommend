# Step 1 Duty Gold - Acceptance Report (v0)

**Status: STEP1_COMPLETE / NOT_ADMITTED / NOT_TRAINING**
Rows: 6 scripts; duty stages total: 41

## Q1 - How many tasks yield a trustworthy duty sequence?

**6 / 6.** Every script satisfies the frozen criterion (>=60% of stages with
provenance in {task_determined, source_required} and at least one
non-source_order_only order basis). All six have task_explicit ordering for
their main chain.

## Q2 - Field provenance counts (over 41 stages)

| provenance | count | share |
|---|---:|---:|
| task_determined | 40 | 98% |
| source_required | 1 | 2% |
| undeterminable | 0 | 0% |

The single source_required stage is the median-composite step in script_275285
(Task never states a compositing step; col.median() is source-only).

**Critical caveat (recorded honestly):** G0 instructions read as code-derived
workflow summaries - they narrate the implementation in execution order. The
high task_determined rate therefore does NOT prove independent human task
intent; it may reflect that the Task text was itself generated from the script.
For training Task->duty this creates a circularity risk: the model may learn to
invert summarization rather than to plan. Any Step-2 design must treat this as
the primary validity threat (e.g., tasks authored independently of code, or
held-out tasks from other sources).

## Q3 - Definition clarity / inter-annotator reproducibility

Ambiguity points encountered, with severity:

1. **Duty granularity** (moderate): RUSLE's five factors could be one
   "factor computation" duty or five; I followed the Task's own enumeration.
   A second annotator applying the same rule (Task-granularity) should agree.
2. **Presentation vs workflow duty** (moderate): charts/Map.addLayer are
   counted as duties when the Task lists them as outputs (269131, 36595,
   93009). Reasonable annotators could exclude them; impact ~1 stage/script.
3. **Composite step** (low): not in the Task text for 275285; the rule says
   source_required, not dropped - the rule is explicit.
4. **C-target count inference** (high for 93009): Task names 2 years, source
   builds 5 (+2 historical layers). Recorded count mismatch instead of forcing
   2 or 5. For 302840 the count (8) is directly listable from the Task.

Overall: B and C definitions are clear enough that a second annotator should
reach substantial agreement on stage identity and order; C-count inference is
reliable only when the Task explicitly enumerates the repeated units.

## C-target results

| script | count inferable | value | homogeneous | binding |
|---|---|---|---|---|
| 302840 | yes | 8 | yes | per-target-variable (task-level; specifics source-only) |
| 93009 | partial | Task=2 vs source=5 | yes | per-year (task-explicit) |
| others | no | - | - | none |

## Conclusion

- B (task->duty) is constructible for all six with explicit evidence chains.
- The dominant validity threat is G0-Task circularity, not annotatability.
- C is viable only where the Task enumerates repeated units (302840 pattern).
