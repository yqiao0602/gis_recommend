# -*- coding: utf-8 -*-
"""MVCS v1 Boundary Annotation — pipelines/ package.

This file is a STUB showing the required module-level boundary annotations
that every pipelines/*.py file MUST carry.

Copy these annotations to the top of each pipelines module:
  interactive_system.py, recommend_pipeline.py,
  demo_complete_pipeline.py, stage2_completion_pipeline.py

DO NOT import this file. It documents the required annotations only.
"""

# === REQUIRED: add this block to EVERY pipelines/*.py file ===

__layer__ = "runtime"                                    # REQUIRED
__allowed_imports__ = [                                  # REQUIRED
    "torch", "torch.nn",
    "json", "sys", "os", "pathlib",
    "gis_recommend.config.transformer_config",
    "gis_recommend.models.transformer_model_v4",
    "gis_recommend.operators.qgis_candidate_generator",
    "gis_recommend.operators.qgis_operator_qa",
    "gis_recommend.knowledge_graph.neo4j_graphrag_retriever",
    "gis_recommend.knowledge_graph.rag_context_builder",
    "gis_recommend.knowledge_graph.chain_validator",
    "gis_recommend.knowledge_graph.chain_repair",
    "gis_recommend.llm.llm_scorer",
    "gis_recommend.llm.llm_extractor",
]
__forbidden_imports__ = [                              # REQUIRED
    "gis_recommend.evidence",                          # MVCS L007-L008
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
    "classify_checkpoint_validity",
    "reconstruct_lineage",
    "recompute_metrics",
    "compare_metrics",
    "diff_dispatch",
    "generate_archaeology_report",
]
