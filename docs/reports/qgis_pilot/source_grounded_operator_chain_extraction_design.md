# Source-Grounded QGIS Operator Chain Extraction Design

Date: 2026-07-16

## Objective

Extract evidence-backed QGIS operator chains from real scripts without forcing every low-level API call or custom workflow into one catalog operator. The output remains a review candidate until its evidence tier passes a measured human-precision gate.

## Why Exact Signature Transfer Is Insufficient

The independent transfer review currently has 2 correct top-1 predictions out of 15 reviewed candidate rows. Generic calls (`gdal.open`), geometry primitives, layer metadata, and WKB helpers transfer implementation similarity instead of operator identity. Exact call overlap must not auto-label workflows.

## Evidence Tiers

1. **E0: Explicit Processing ID**
   - Extract literal IDs from `processing.run`, `QgsProcessingAlgorithm` calls, command wrappers, and equivalent AST constants.
   - Example: `qgis:hypsometriccurves`.
   - Candidate for automatic acceptance only after a stratified precision audit.

2. **E1: Self-Describing Algorithm Class**
   - Read class base/provider plus constant returns from `name()`, `displayName()`, `groupId()`, and parameter/output schema.
   - Resolve the resulting ID exactly against the operator catalog.
   - Example: `GeometryConvert.name()=convertgeometrytype` -> `qgis:convertgeometrytype`.

3. **E2: Ordered Direct-API Semantic Chain**
   - Build a statement-ordered call graph with argument roles, variable/data dependencies, and produced/consumed artifacts.
   - Aggregate API sequences into operation families such as raster calculation, rasterization, reprojection, overlay, simplify, zonal statistics, export, and CRS transformation.
   - Match families to catalog operators using provider, modality, input/output schema, parameters, and task text. Shared calls alone cannot create a label.

4. **E3: Custom or Unbounded Workflow**
   - Preserve the class/function identity and a grounded semantic chain when no standard catalog operator covers the task.
   - Examples: `ImportEnmapL1CAlgorithm`, `UrbanSummaryWorker`, `InfiltrationCalculator|GreenAmpt|SCPCurveNumber`.
   - Do not invent a standard operator ID. Map only independently supported substeps.

## Extraction Pipeline

1. Resolve immutable source path/hash and reject provenance collisions.
2. Parse AST and ordered steps while retaining statement index, scope, arguments, class, provider, parameters, and outputs.
3. Extract explicit Processing IDs and self-describing class IDs before any fuzzy inference.
4. Segment scripts into functions/classes and data-dependent workflow regions.
5. Compile direct API calls into semantic operation families using reviewed deterministic rules.
6. Produce catalog candidates constrained by provider, modality, parameter schema, input/output types, and the experimental taxonomy.
7. Use task text only as a consistency/reranking signal, never as the sole label source.
8. Emit a chain, confidence by step, unsupported/custom steps, and complete evidence IDs; abstain when evidence is insufficient.
9. Optionally use an LLM only for bounded candidate comparison or grounded task-description generation. It may not add, remove, or reorder unsupported operations.
10. Keep all derived rows train-only and source-grouped until human review and leakage checks pass.

## Proposed Validation Gates

- Start with the existing 50-row transfer review as regression cases.
- Build a new approximately 300-row stratified pilot covering explicit IDs, self-describing classes, direct API, custom workflows, vector/raster/mixed modality, and operation families.
- Report precision separately for E0, E1, E2, and custom-abstention handling. Coverage is never accuracy.
- Do not scale or create training rows until each admitted tier has an approved precision threshold and no repeated high-severity failure mode.
- Re-audit a stratified sample after every large batch.

## Output Contract

Each candidate must retain source path/hash, evidence tier, ordered evidence IDs, operator chain, custom/unbounded steps, parameters and I/O roles, confidence, task-text provenance, reviewer status, taxonomy admission, and training admission. The default for taxonomy and training admission is `not_granted`.

## Scale Expectation

This design can be applied to the wider script corpus, but the final usable count cannot be inferred from the raw 398k scripts or the current 5,107 eligible records. E0/E1 should provide the highest-precision subset; E2 determines whether coverage can grow materially. The 20k training-row target should be evaluated only after deduplicated grounded chains and at most bounded, evidence-preserving text variants are measured.
