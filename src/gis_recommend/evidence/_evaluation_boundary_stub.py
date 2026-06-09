# -*- coding: utf-8 -*-
"""MVCS v1 Boundary Annotation — evaluation/ package.

This file is a STUB showing the required module-level boundary annotations
for evaluation/*.py files.

Evaluation scripts may READ checkpoint data for reporting purposes
but MUST NOT mutate snapshots or gate runtime behavior based on
interpretive outputs.

Copy these annotations to the top of each evaluation module that
touches checkpoint files: runner.py, report.py, diagnostics.py
"""

# === REQUIRED: add this block to evaluation modules that read checkpoints ===

__layer__ = "runtime"                                    # REQUIRED
__allowed_imports__ = [                                  # REQUIRED
    "torch",
    "json", "sys", "os", "pathlib", "datetime",
    "gis_recommend.config.transformer_config",
    "gis_recommend.evidence",                          # ALLOWED for evaluation —
    "gis_recommend.evidence._schemas",                 # evaluation may produce
    "gis_recommend.evidence._validity",                # reports but never gates
    "gis_recommend.evidence._compare",
]
__forbidden_imports__ = [                              # REQUIRED
    "gis_recommend.evidence._provenance._build",       # never build provenance in eval
    "gis_recommend.evidence._metric_bundle._build",    # never build metric_bundle in eval
]
__snapshot_access__ = [                                # REQUIRED
    # Read-only access for reporting:
    "checkpoint['provenance']",                        # ALLOWED:interpretive_input_only
    "checkpoint['metric_bundle']",                     # ALLOWED:interpretive_input_only
    # NEVER modify and re-save (MVCS L026):
    # torch.load(X); modify; torch.save(X) → SnapshotModificationViolation
]
