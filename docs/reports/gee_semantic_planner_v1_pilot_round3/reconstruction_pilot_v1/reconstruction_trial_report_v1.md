# R1-R4 Single-Script Reconstruction Trial — script_36595 (RUSLE)

**Status: TRIAL_COMPLETE / METHOD_VALIDATION_ONLY / NOT_GOLD / NOT_TRAINING**

## 1. R1 variable-level dataflow

- Variables recovered: 21, each with honest definition_location: 14 in_source, 5 external_input (soil/elevation/s2/lulc/dataset-origin; first_use recorded separately from definition)
- Dataflow edges: 21 — 17 with full in-source definition evidence, 4 whose source variable is externally prebound (use+passing evidence confirmed; source-side definition honestly marked unavailable, not fabricated)
- No order-only edges. First-use lines are never presented as definition lines.

Key recovery vs G0 chain: factor identities R, K, LS, C, P exist as named
variables with located definitions — exactly the identity information the
mapping layer lost (k_factor/ls_factor/p_factor were mapping_loss in the
reconciliation; r/c factors were representation_gap).

## 2. R2 duty/operation separation

- 11 units, each with task_duty / source_operation / provenance / implementation_detail
- provenance: task_determined 10, source_required 1
- implementation details that WOULD change under another implementation: 9 — all confined to the detail field
- misassigned to task_duty: 0

Example of the separation working: "train with a Random Forest" style
fixations are avoided — e.g., the C-factor's exp-transform normalization is
recorded as an implementation choice, while the task duty is only "compute
the vegetation cover (C) factor".

## 3. R3 relationships (revised: four relation types kept separate)

- dataflow edges: 21 (4 passing-only with external-source caveat)
- **task_enumeration_order: 5** — the task's textual listing order of R,K,LS,C,P is preserved as TEXT evidence only; it is NOT promoted to workflow_sequence, because the five factors are independently preparable and natural-language enumeration does not establish execution dependency
- workflow_sequence: 4 — 3 task_explicit (task verbatim) + 1 task_implied (semantic/dataflow inference, not verbatim ordering)
- semantic_dependency: factor→product and product→statistics edges, task-supported
- semantic_merge vs control structure: the {R,K,LS,C,P}→soil_loss combination is recorded as `semantic_merge` (task explicitly names it), explicitly NOT as a source control-flow merge — dataflow fan-in alone does not make a merge
- control structures: 3 candidates, all conservatively classified

## 4. R4 four-dimension acceptance

| dimension | result |
|---|---|
| semantic recovery | 7/7 audit units recovered (denominator = this script's 7 units, pre-registered) |
| evidence traceability | 17/21 edges with full three-condition support; 4 passing-only (external prebinding); 0 disguised |
| task reasonableness | fixation rate 0/11 = 0.0; 0 undeterminable |
| gold comparison (diagnostic) | 9/9 gold stages covered; reconstruction adds 1 source_required unit; diagnostic only — circularity caveat recorded |

## 5. Failure analysis

- extraction misses: 0 (all 7 audit-unit operations located in source)
- variable trace failures: 2 (external prebindings, outside script scope)
- duty merge errors: 0; relation misjudgments: 0 (factor-order workflow_sequence claims removed in this revision)
- insufficient task evidence: 1 (basin_mean_statistic — correctly classified source_required, not task_duty)

## 6. Revision record (owner review fixes #1-#3 applied)

1. **External variable definition locations corrected**: soil/elevation/s2/lulc changed from fabricated def_line to `definition_location: unavailable_in_source` + `first_use_line`; their edges carry use+passing evidence with source-definition honestly marked unavailable
2. **Factor enumeration order separated from workflow order**: task's R→K→LS→C→P listing preserved as task_enumeration_order text evidence; factor-to-factor workflow_sequence claims withdrawn; the five factors keep their semantic_dependency edges into the product
3. **semantic_merge separated from control flow**: the product combination recorded as a semantic relation (`relation_type: semantic_merge`, `control_structure: not_a_control_merge`), no longer implying source-level control-flow merge

## 7. Answer to the pilot question

The reconstruction rules recover the factor identities, dependency structure
(R,K,LS,C,P → soil_loss; product → class → statistics) and task-vs-implementation
separation that the G0 mapping layer destroyed — without promoting any
implementation choice (lookup tables, polynomial coefficients, NDVI transform
form, export fields) into a task requirement, and without copying the task's
sentence order into a factor execution chain.

Method validity: demonstrated on this representative script. Generalization to
other GEE scripts is NOT established; expansion requires a separate ruling.

## 8. Stop

No training, no inference, no further scripts. Output is method-validation
evidence and supervision candidate material only.
