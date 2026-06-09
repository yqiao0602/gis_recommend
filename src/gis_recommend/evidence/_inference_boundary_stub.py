# -*- coding: utf-8 -*-
"""MVCS v1 Boundary Annotation — inference/ package.

This file is a STUB showing the required module-level boundary annotations
that every inference/*.py file MUST carry.

Copy these annotations to the top of each inference module:
  infer_l3_candidates.py, infer_l3_candidates_v4.py, infer_task_conditioned_v3.py

DO NOT import this file. It documents the required annotations only.
"""

# === REQUIRED: add this block to EVERY inference/*.py file ===

__layer__ = "runtime"                                    # REQUIRED
__allowed_imports__ = [                                  # REQUIRED
    "torch", "torch.nn", "torch.nn.functional",
    "numpy", "json", "math",
    "pathlib", "sys", "os", "collections",
    "tqdm", "transformers",
    "gis_recommend.config.transformer_config",
    "gis_recommend.models.transformer_model_v4",
    "gis_recommend.models.task_text_processor",
]
__forbidden_imports__ = [                              # REQUIRED
    "gis_recommend.evidence",                          # MVCS L003-L004
    "gis_recommend.evidence._provenance",
    "gis_recommend.evidence._metric_bundle",
    "gis_recommend.evidence._validity",
    "gis_recommend.evidence._lineage",
    "gis_recommend.evidence._recompute",
    "gis_recommend.evidence._compare",
    "gis_recommend.evidence._archaeology",
    "gis_recommend.evidence._schemas",
    "gis_recommend.evidence._boundary",
]
__forbidden_methods__ = [                              # REQUIRED
    "classify_checkpoint_validity",                    # MVCS L015
    "reconstruct_lineage",
    "recompute_metrics",
    "compare_metrics",
    "diff_dispatch",
    "generate_archaeology_report",
]
__snapshot_access__ = [                                # REQUIRED
    # Only model_state_dict via torch.load for inference:
    "checkpoint['model_state_dict']",                  # ALLOWED:load_only
    # FORBIDDEN: provenance, metric_bundle, selector_policy, decode_policy
]
