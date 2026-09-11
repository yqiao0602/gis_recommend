# QGIS Planner Benchmark v0.1 Supported-Scope Freeze

## Status

This profile is a one-week delivery profile for the formal QGIS planner
benchmark. It narrows the supported claim without rewriting the original v1.0
Gate 3 result. The original profile remains `failed_insufficient_candidate_supply`;
this profile is an explicit, smaller release authority.

## Goal

Deliver a reproducible benchmark for the paper question:

> Can a system map a natural-language GIS task to a reliable, parameter-free
> QGIS operator dependency graph?

The model-visible task is natural language. The primary gold is only QGIS
`processes + links`. Concrete files, parameters, fields, CRS values, thresholds,
and output destinations remain outside the planner task.

## Release Contents

The v0.1 freeze contains:

- 40 development task records;
- 120 sealed final task records;
- 12-20 separate refusal diagnostic records;
- authority, gold, review, scorer, manifest, and checksum files.

The 160 supported records are task instances, not 160 independent workflows.
The current authority supplies 52 distinct normalized DAGs. The release must
report both task-level counts and distinct-DAG counts.

## Supported Scope

Headline claims are limited to parameter-free vector/mixed QGIS planning with
linear and multi-input-merge dependency graphs. The current supply contains no
branch DAGs, so v0.1 makes no branch or multi-output capability claim.

Raster records are retained only as exploratory coverage. One-step records and
singleton families are descriptive and cannot support family-level ranking.
The eight families with at least three independent DAGs are repeat-supported;
families with fewer DAGs are reported as coverage, not statistically reliable
family results.

The original stable101 taxonomy, strict catalog, mapping authority, and Gate 2
exclusion rules remain in force. The profile changes only the release scope and
does not promote a diagnostic operator or synthesize missing supply.

## DAG-Grouped Split

Selection is made at the distinct DAG level, never at the candidate-row level:

- development target: 8 canonical DAGs, five independently authored task
  variants per DAG;
- final target: 40 canonical DAGs, three independently authored task variants
  per DAG;
- reserve: four pre-reviewed canonical DAGs, held outside both splits.

If annotation rejects a DAG, substitutions come only from the predeclared
reserve. If the reserve is exhausted, the freeze fails closed rather than
copying a graph across splits or weakening the semantic gate.

All variants of one `canonical_graph_id` remain in the same split. The graph
identity and `variant_id` are non-model-visible. A variant is a distinct
natural-language task instance only when its intent and output constraint are
independently reviewed; superficial synonym replacement does not create a new
instance.

The final report uses task-level metrics and DAG-clustered macro metrics. Any
confidence interval or significance test treats variants of one DAG as a single
cluster; three variants must not be presented as three independent workflows.

## Record Separation

Every supported sample uses `sample_id` as its only cross-file join key:

1. `tasks.jsonl`: model-visible `sample_id` and independently authored
   `task_text` only;
2. `gold_graphs.jsonl`: canonical graph, accepted alternatives, required
   operators, required edges, precedence, optional nodes, and reviewed
   commutativity;
3. `authority_sidecar.jsonl`: source/DAG hashes, stable101 and catalog
   authority, `canonical_graph_id`, `variant_id`, `task_intent`,
   `output_constraint`, process necessity, provenance, and review evidence;
4. `reviews.jsonl`: reviewer identities, decisions, disagreements, and
   adjudication;
5. `manifest.json` and `checksums.sha256`: immutable version and artifact
   evidence.

Semantic fields are authority evidence. They must never be copied into the
model-visible task or the primary `processes + links` gold contract.

## Semantic Closure

Before task variants are authored, every selected DAG receives an independent
QGIS graph review. The review must establish:

- every operator is strict-catalog and stable101 admitted;
- every link is connected, acyclic, and type-compatible;
- the graph has a coherent task intent and output constraint;
- every retained process is necessary or explicitly optional;
- any accepted alternative, commutable pair, or precedence relation is frozen.

Multi-input merge graphs receive two independent graph reviews. Any graph with
unresolved intent, output type, or process necessity is returned or replaced by
reserve; it cannot be repaired after final predictions are viewed.

Each task variant receives a semantic text review against the frozen graph.
Final rows receive primary review; at least 25% receive blind independent
second review, and all disagreements are adjudicated before sealing.

## Leakage Boundary

Final rows must be disjoint from training, validation, historical audit, prompts,
and development by all authority keys already frozen in Gate 2:

- source SHA;
- normalized source body;
- AST/source region;
- owner/call-graph signature;
- exact DAG and forbidden near-DAG;
- semantic DAG signature;
- derived task-text signature and task-token signature.

The same operator family may appear in multiple splits. The source/DAG group,
not a random row, is the isolation unit.

## Refusal Diagnostic

Refusal is a separate diagnostic denominator. It contains only unsupported
capabilities and materially underspecified goals. Missing concrete parameters
alone never creates a refusal. Refusal records use explicit reason codes and
are not mixed into graph-planning metrics.

## Relationship To Training Data

Directly taking a random slice from training data is an IID engineering holdout:
it can share source bodies, cloned templates, DAGs, task text, or generation
artifacts with training and may measure memorization.

Training-derived evidence may seed this benchmark only after the full benchmark
pipeline is applied: Gate 2 group exclusion, independent task authoring,
parameter-free graph projection, alternative-aware gold review, semantic text
review, sealed final split, and version/hash freeze. Once those steps are done,
the result is benchmark authority derived from training evidence, not a direct
train/test split.

## One-Week Gates

1. Restore and hash-lock Gate 3 authority (`149` candidates, `90` source
   authorities, `52` distinct DAGs; original full-quota failure retained).
2. Review and select the 8/40/4 DAG roster; reject or reserve ambiguous graphs.
3. Author and review 40 development tasks and 120 final tasks without exposing
   final gold to model or prompt tuning.
4. Run source, DAG, near-DAG, semantic-text, and task-token leakage checks.
5. Freeze scorer, seal final gold, build manifest/checksums, and rebuild twice
   to prove byte identity.

## Explicit Non-Claims

v0.1 does not claim balanced coverage of all stable101 families, raster parity,
branch planning, parameter binding, executable workflow correctness, or 160
independent workflows. Those require a later benchmark version with additional
independent DAG supply.
