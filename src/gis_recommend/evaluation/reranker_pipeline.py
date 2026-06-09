# -*- coding: utf-8 -*-
"""L3 / QGIS inference orchestration and reranker candidate pool construction.

Extracted from scripts/evaluate_system.py (2026-04-16). Central place for
any logic that runs the end-to-end recommendation pipeline (excluding the
Rerank algorithm itself, which lives in gis_recommend.reranking).

Public API:
    tokens_to_l3_codes
    get_set_predictor_tokens
    is_better_l3_source
    build_reranker_candidate_pool      (v2 — dedupes by QGIS chain)
    build_reranker_candidate_pool_v3   (v3 — keeps all (QGIS, L3) pairs)
    select_qgis_candidate_for_evaluation
    run_l3_inference
    run_qgis_evaluation
"""
from __future__ import annotations

from pathlib import Path

import torch
from tqdm import tqdm

from gis_recommend.config.transformer_config import (
    V4_6_TRANSFORMER_CHECKPOINT_DIR,
    SET_PREDICTOR_CHECKPOINT_DIR,
)
from gis_recommend.evaluation.semantic_metrics import (
    ChainMetrics, compute_chain_metrics,
)


def tokens_to_l3_codes(tokens: list[int], id_to_l3_code: dict[int, str]) -> list[str]:
    """Convert token ids to L3 codes, skipping unknown ids."""
    return [id_to_l3_code[t] for t in tokens if t in id_to_l3_code]


def get_set_predictor_tokens(inferencer, model_inputs: dict, effective_set_prior_mode: str):
    """Return token presence probabilities for reranker features."""
    if effective_set_prior_mode == "off" or inferencer.set_predictor is None:
        return None

    try:
        scores = inferencer.set_predictor.predict_token_scores(
            model_inputs["task_type_id"],
            model_inputs["text_input_ids"],
            model_inputs["text_attention_mask"],
        )
        return scores[0]
    except Exception as e:
        print(f"  [WARN] Failed to predict set-prior scores for reranker: {e}")
        return None


def is_better_l3_source(new_l3_candidate, current_l3_candidate) -> bool:
    """Prefer the stronger L3 source when two L3 candidates map to one QGIS chain."""
    new_score = getattr(new_l3_candidate, "final_score", float("-inf"))
    current_score = getattr(current_l3_candidate, "final_score", float("-inf"))
    if new_score != current_score:
        return new_score > current_score

    new_length = getattr(new_l3_candidate, "length", 10**9)
    current_length = getattr(current_l3_candidate, "length", 10**9)
    return new_length < current_length


def build_reranker_candidate_pool(
    all_l3_candidates: list,
    id_to_l3_code: dict[int, str],
    qgis_generator,
    per_l3_top_k: int = 3,
) -> tuple[list, list]:
    """Build the N x M reranker pool and dedupe by QGIS chain (v2 mode)."""
    best_by_chain: dict[tuple[str, ...], tuple] = {}

    for l3_candidate in all_l3_candidates:
        l3_codes = tokens_to_l3_codes(l3_candidate.tokens, id_to_l3_code)
        if not l3_codes:
            continue

        try:
            qgis_candidates = qgis_generator.generate_candidates(l3_codes, top_k=per_l3_top_k)
        except Exception:
            continue

        for qgis_candidate in qgis_candidates:
            chain_key = tuple(qgis_candidate.qgis_sequence)
            existing = best_by_chain.get(chain_key)
            if existing is None or is_better_l3_source(l3_candidate, existing[1]):
                best_by_chain[chain_key] = (qgis_candidate, l3_candidate)

    ranked_pairs = sorted(
        best_by_chain.values(),
        key=lambda pair: (
            getattr(pair[1], "final_score", 0.0),
            getattr(pair[0], "score", 0.0),
            getattr(pair[0], "confidence", 0.0),
        ),
        reverse=True,
    )
    return [pair[0] for pair in ranked_pairs], [pair[1] for pair in ranked_pairs]


def build_reranker_candidate_pool_v3(
    all_l3_candidates: list,
    id_to_l3_code: dict[int, str],
    qgis_generator,
    per_l3_top_k: int = 3,
) -> tuple[list, list, list]:
    """Build reranker pool WITHOUT dedup — keep all (QGIS, L3) pairs with beam rank.

    Returns:
        (pool_qgis, pool_l3, beam_ranks) — beam_ranks[i] is the 0-based index of
        pool_l3[i] in the original all_l3_candidates list (i.e. the beam rank).
    """
    pool_qgis = []
    pool_l3 = []
    beam_ranks = []

    for beam_rank, l3_candidate in enumerate(all_l3_candidates):
        l3_codes = tokens_to_l3_codes(l3_candidate.tokens, id_to_l3_code)
        if not l3_codes:
            continue

        try:
            qgis_candidates = qgis_generator.generate_candidates(l3_codes, top_k=per_l3_top_k)
        except Exception:
            continue

        for qgis_candidate in qgis_candidates:
            pool_qgis.append(qgis_candidate)
            pool_l3.append(l3_candidate)
            beam_ranks.append(beam_rank)

    return pool_qgis, pool_l3, beam_ranks


def select_qgis_candidate_for_evaluation(l3_res: dict, generator):
    """Return the QGIS candidate that should be evaluated for one sample."""
    selected = l3_res.get("selected_qgis_candidate")
    if selected is not None:
        return selected

    pred_codes = l3_res.get("pred_codes", [])
    if not pred_codes:
        return None

    candidates = generator.generate_candidates(pred_codes)
    return candidates[0] if candidates else None


def run_l3_inference(
    test_set: list,
    device: torch.device,
    checkpoint_path: str = None,
    disable_topk: bool = False,
    set_prior_mode: str = 'soft',
    sp_checkpoint: str = None,
) -> tuple[list, dict]:
    """Run L3 beam search inference for each test sample.

    Returns:
        (l3_results, infer_meta): results per sample + inference config metadata
    """
    from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

    if checkpoint_path:
        checkpoint = Path(checkpoint_path)
    else:
        checkpoint = V4_6_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
        print(f"  [WARN] No --checkpoint specified, defaulting to V4.6: {checkpoint}")
    sp_path = Path(sp_checkpoint) if sp_checkpoint else (SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth")
    print(f"  Loading inferencer from {checkpoint} ...")
    inferencer = L3SequenceInferencerV4(
        checkpoint_path=checkpoint,
        device=device,
        set_predictor_path=sp_path,
    )
    inferencer.set_prior_mode = set_prior_mode
    print(f"  [Set Predictor] prior mode = {set_prior_mode}")
    if disable_topk and set_prior_mode == 'hard':
        inferencer.use_topk_set_prediction = False
        print(f"  [Set Predictor] Top-K disabled, using threshold mode (hard only)")

    set_predictor_loaded = inferencer.set_predictor is not None
    effective_set_prior_mode = set_prior_mode if (set_predictor_loaded or set_prior_mode == 'off') else 'off'
    if set_prior_mode != 'off' and not set_predictor_loaded:
        print("  [WARN] Set predictor unavailable; constraints disabled for this run")

    infer_meta = {
        "transformer_checkpoint": str(checkpoint),
        "set_predictor_checkpoint": str(sp_path),
        "set_predictor_loaded": set_predictor_loaded,
        "requested_set_prior_mode": set_prior_mode,
        "effective_set_prior_mode": effective_set_prior_mode,
        "use_topk_set_prediction": bool(inferencer.use_topk_set_prediction),
        "set_predictor_use_rich_cross_attn": (
            bool(inferencer.set_predictor.use_rich_cross_attn) if set_predictor_loaded else None
        ),
        "set_predictor_num_active_tokens": (
            int(inferencer.set_predictor.num_active_tokens) if set_predictor_loaded else 0
        ),
    }

    results = []
    for sample in tqdm(test_set, desc="L3 inference", unit="sample"):
        tt = sample["task_type"]
        desc = sample["task_description"]
        name = sample["task_name"]

        inferencer.set_expected_length(tt)

        model_inputs = inferencer._prepare_input(name, desc, tt)
        set_predictor_tokens = get_set_predictor_tokens(
            inferencer,
            model_inputs,
            effective_set_prior_mode,
        )

        candidates = inferencer.infer_from_model_input(
            model_inputs,
            task_type=tt,
            mode="beam",
        )

        pred_tokens = candidates[0].tokens if candidates else []
        pred_codes = tokens_to_l3_codes(pred_tokens, inferencer.id_to_l3_code)
        top_l3_score = candidates[0].final_score if candidates else 0.0

        results.append({
            "pred_tokens": pred_tokens,
            "pred_codes": pred_codes,
            "pred_score": top_l3_score,
            "pred_l3_score": top_l3_score,
            "baseline_pred_tokens": list(pred_tokens),
            "baseline_pred_codes": list(pred_codes),
            "baseline_pred_score": top_l3_score,
            "reranker_score": None,
            "num_candidates": len(candidates),
            "all_candidates": candidates,
            "all_candidates_tokens": [c.tokens for c in candidates],
            "all_candidates_scores": [c.final_score for c in candidates],
            "expected_length": inferencer.expected_length,
            "set_predictor_tokens": set_predictor_tokens,
            "reranker_pool_size": 0,
            "reranker_features": None,
            "selected_qgis_candidate": None,
            "selected_qgis_chain": None,
            "selected_from_reranker": False,
        })

    return results, infer_meta


def run_qgis_evaluation(
    test_set: list,
    l3_results: list,
    run_contract=None,
) -> list:
    """Run QGIS candidate generation + chain validation."""
    from gis_recommend.operators.qgis_candidate_generator import QGISCandidateGenerator
    from gis_recommend.knowledge_graph.neo4j_graphrag_retriever import Neo4jGraphRAGRetriever
    from gis_recommend.knowledge_graph.chain_validator import ChainValidator

    print("  Initializing QGIS generator ...")
    generator = QGISCandidateGenerator(run_contract=run_contract, verbose=False)

    print("  Connecting to Neo4j ...")
    retriever = Neo4jGraphRAGRetriever()
    validator = ChainValidator(retriever)

    chain_results = []
    sample_pairs = zip(test_set, l3_results)
    for i, (sample, l3_res) in enumerate(
        tqdm(sample_pairs, total=len(test_set), desc="QGIS evaluation", unit="sample")
    ):
        selected_chain = l3_res.get("selected_qgis_chain")
        if selected_chain:
            qgis_chain = selected_chain
            selected_cand = l3_res.get("selected_qgis_candidate")
            unknown_ratio = selected_cand.unknown_ratio if selected_cand else 0.0
            unknown_count = selected_cand.unknown_count if selected_cand else 0
        else:
            pred_codes = l3_res["pred_codes"]
            if not pred_codes:
                chain_results.append(ChainMetrics().to_dict())
                continue
            try:
                candidates = generator.generate_candidates(pred_codes)
            except Exception as e:
                print(f"    [WARN] QGIS generation failed for sample {i}: {e}")
                chain_results.append(ChainMetrics().to_dict())
                continue
            if not candidates:
                chain_results.append(ChainMetrics().to_dict())
                continue
            top = candidates[0]
            qgis_chain = top.qgis_sequence
            unknown_ratio = top.unknown_ratio
            unknown_count = top.unknown_count

        try:
            val_result = validator.validate_chain(qgis_chain)
            metrics = compute_chain_metrics(qgis_chain, val_result)
        except Exception as e:
            print(f"    [WARN] Chain validation failed for sample {i}: {e}")
            metrics = ChainMetrics(
                coverage=1.0 - unknown_ratio,
                total_steps=len(qgis_chain),
                unknown_count=unknown_count,
            )

        result = metrics.to_dict()
        result["qgis_chain"] = qgis_chain
        if selected_chain:
            selected_cand = l3_res.get("selected_qgis_candidate")
            result["qgis_score"] = selected_cand.score if selected_cand else 0.0
            result["qgis_confidence"] = selected_cand.confidence if selected_cand else 0.0
        else:
            result["qgis_score"] = top.score
            result["qgis_confidence"] = top.confidence
        chain_results.append(result)

    try:
        retriever.close()
    except Exception:
        pass

    return chain_results
