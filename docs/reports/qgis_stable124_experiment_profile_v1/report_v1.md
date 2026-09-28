# Stable124 Experimental Profile v1

This is an isolated experiment package for the controlled comparison:

`stable124 baseline` versus `stable124 baseline + 28 curated QGIS rows`.

The production `v2_94_stable` package and all official authority/evaluation
artifacts remain unchanged. The baseline contains the original 76,884 rows and
the augmented package contains those rows plus the complete 28-row curated
train-only QGIS corpus. The original validation and test index lists are reused
verbatim; only the train list receives indices 76,884 through 76,911.

The profile uses 124 content-token IDs and 128 model IDs after the four special
tokens. IDs 0-93 and their embedding rows are preserved exactly. Rows 94-123
are initialized with deterministic CPU `torch.randn` using seed `124256`.
`stable124_experimental` is available through `GIS_VOCAB_PROFILE` and is never
selected by the production default.

## Baseline composition census

An exact census of the actual `operator_sequence` field shows that all 76,884
baseline rows contain only `ee.*` operators (GEE-only); there are no non-GEE or
empty sequences. QGIS appears only in the appended increment: 19 `QGIS Silver
Processing 工作流` rows and 9 `QGIS 源码派生子工作流` rows. The experiment task
vocabulary extends the 47 baseline task types to 49, assigning the two QGIS
types IDs 47 and 48 rather than encoding them as `Unknown`. See
`baseline_composition_v1.json`.

Verification completed:

- profile builder completed and wrote the manifest with input hashes;
- baseline and +28 training entrypoints passed dry-run preflight;
- profile tests: 5 passed (`pytest -q tests/test_build_qgis_stable124_experiment.py`);
- no model training or checkpoint write was performed.

## Interpretation boundary

This package is a controlled data-path and augmentation experiment, not a
platform-balance experiment. The baseline is empirically GEE-only by its
operator prefixes; the 28 QGIS rows are an appended train-only increment. The
experiment therefore tests whether the curated QGIS increment can be consumed
without breaking the stable124 pipeline, and whether it produces a measurable
QGIS-specific or regression signal under a fixed evaluation setup. It does not
show that 28 rows are sufficient for a QGIS workflow corpus, nor does it
estimate the relative value of GEE and QGIS from row counts alone.

The historical figure of 8,283 GEE rows refers to an independently verified
subset in an earlier GEE processing context. It is not used to decompose the
76,884-row baseline here. Any future corpus comparison must use a fresh,
source-level census with explicit provenance rather than importing that
historical subtotal.

### Number authority

| Number | Status in this experiment |
| ---: | --- |
| 76,884 | Verified row count of the stable124 baseline input |
| 28 | Verified curated QGIS rows appended to train only (20 Gold, 8 Silver) |
| 76,912 | Verified augmented row count |
| 19 / 9 | Verified QGIS increment split: Processing rows / source-derived subworkflow rows |
| 455 | Historical Processing admission candidate pool; not a row count in this package |
| 508 | Separate QGIS authority count; not the stable124 baseline or augmented count |
| 47,852 | Historical QGIS raw-source census; not a count of this training package |
| 8,283 | Historical GEE train-only subset; not a decomposition of the 76,884 baseline |

Only the first three counts are used as A/B package counts. The historical
counts are retained for provenance and must not be used to infer current source
shares or expected yield.
