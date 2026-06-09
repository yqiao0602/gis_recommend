# -*- coding: utf-8 -*-
"""MVCS v1 Boundary Annotation — models/ package.

This file is a STUB showing the required module-level boundary annotations
that every models/*.py file MUST carry.

Copy these annotations to the top of each models module:
  transformer_model_v3.py, transformer_model_v4.py,
  task_text_processor.py, set_predictor_v3.py

DO NOT import this file. It documents the required annotations only.
"""

# === REQUIRED: add this block to EVERY models/*.py file ===

__layer__ = "runtime"                                    # REQUIRED
__allowed_imports__ = [                                  # REQUIRED
    "torch", "torch.nn", "torch.nn.functional",
    "math", "typing",
    "transformers",
]
__forbidden_imports__ = [                              # REQUIRED
    "gis_recommend.evidence",                          # MVCS L005-L006
    "gis_recommend.evidence._provenance",
    "gis_recommend.evidence._metric_bundle",
    "gis_recommend.evidence._validity",
    "gis_recommend.evidence._lineage",
    "gis_recommend.evidence._recompute",
    "gis_recommend.evidence._compare",
    "gis_recommend.evidence._archaeology",
    "gis_recommend.evidence._schemas",
    "gis_recommend.evidence._boundary",
    "gis_recommend.training",
    "gis_recommend.inference",
]
__forbidden_methods__ = [                              # REQUIRED
    "classify_checkpoint_validity",
    "reconstruct_lineage",
    "recompute_metrics",
    "compare_metrics",
    "diff_dispatch",
    "generate_archaeology_report",
]
