# -*- coding: utf-8 -*-
"""MVCS v1 Boundary Annotation — training/ package.

This file is a STUB showing the required module-level boundary annotations
that every training/*.py file MUST carry.

Copy these annotations to the top of each training module:
  train_v4_2.py, train_v4_3.py, train_v4_4.py, train_v4_5.py, train_v4_6.py,
  train_v3.py, train_set_predictor_v3.py, transformer_dataset.py, splits.py

DO NOT import this file. It documents the required annotations only.
"""

# === REQUIRED: add this block to EVERY training/*.py file ===

__layer__ = "runtime"                                    # REQUIRED
__allowed_imports__ = [                                  # REQUIRED
    "torch", "torch.nn", "torch.nn.functional",
    "torch.optim", "torch.amp", "torch.cuda",
    "torch.utils.data",
    "numpy", "json", "math", "hashlib", "random", "time",
    "pathlib", "sys", "os", "collections",
    "tqdm", "transformers",
    "gis_recommend.config.transformer_config",
    "gis_recommend.models.transformer_model_v4",
    "gis_recommend.models.task_text_processor",
    "gis_recommend.training.transformer_dataset",
    "gis_recommend.training.splits",
    "gis_recommend.training.train_v4_2",     # base class
    "gis_recommend.training.train_v4_4",     # warmstart helper
    "gis_recommend.training.train_v4_5",     # sampler
]
__forbidden_imports__ = [                              # REQUIRED
    "gis_recommend.evidence",                          # MVCS L001-L002
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
    "classify_checkpoint_validity",                    # MVCS L009-L010
    "reconstruct_lineage",
    "recompute_metrics",                               # MVCS L011-L012
    "compare_metrics",
    "diff_dispatch",                                   # MVCS L013-L014
    "generate_archaeology_report",
]
__snapshot_access__ = [                                # REQUIRED
    # Only these checkpoint keys may be accessed at runtime:
    "checkpoint['model_state_dict']",                  # ALLOWED:load_only
    "checkpoint['task_classifier_state_dict']",        # ALLOWED:load_only
    "checkpoint['epoch']",                             # ALLOWED:display_only
    "checkpoint['model_config']",                      # ALLOWED:display_only
    "checkpoint['val_loss']",                          # ALLOWED:display_only
    "checkpoint['ar_token_acc']",                      # ALLOWED:display_only
    "checkpoint['ar_seq_em']",                         # ALLOWED:display_only
    # FORBIDDEN: provenance, metric_bundle (MVCS L022-L025)
]
