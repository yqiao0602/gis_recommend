# GEE Extractor v2 P3-A: NewExpression classifier-chain repair

This is a narrow P3 extractor repair. It does not re-extract the 50-row GEE
review pack, does not admit any deferred rows, does not create validation/test
rows, and does not train.

## What changed

- `src/gis_recommend/data/gee_source_extractor.py` now handles ESTree
  `NewExpression` nodes.
- Extractor version is now `gee-source-extractor-v2.0.3`.
- Regression test:
  `tests.test_gee_source_extractor.GeeSourceExtractorTests.test_new_classifier_factory_train_chain_is_not_dynamic`.

## Red/green evidence

Before the fix, the regression case
`new ee.Classifier.smileRandomForest(100).train(training)` produced:

- ordered calls: `[null, "image.classify"]`
- quality issue: `dynamic_callee`

After the fix, it produces:

- `ee.Classifier.smileRandomForest`
- `ee.Classifier.smileRandomForest.train`
- `image.classify`

and no `dynamic_callee` flag for that classifier chain.

## Boundary

This repair is necessary for source-grounded GEE coverage, but it does not by
itself rescue the 28 `extractor_repair_required` rows. Several current ML
deferred snippets use the non-`new` form
`ee.Classifier.smileRandomForest(...).train(...)`, which was already extractable.
Their remaining gaps require a P3-B before/after pass: re-extract the deferred
rows from full source/AST with v2.0.3, compare recovered core calls with the old
retained chains, and then decide which rows can enter P4 rereview.

## Current admission

- Training admission: `not_granted`
- Validation/test admission: `not_granted`
- Production merge: `not_granted`
- LLM used: no
- Training run: no
