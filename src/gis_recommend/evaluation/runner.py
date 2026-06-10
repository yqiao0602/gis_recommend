# -*- coding: utf-8 -*-
"""
Evaluation pipeline V3 for the GIS operator recommendation system — CLI entry.

Stages evaluated:
  1. LLM task extraction — task_type accuracy (if ground truth available)
  2. L3 sequence generation — SeqSim, OrderedSim, L2 accuracy, LCS, token accuracy, EM
  3. QGIS chain quality — coverage, validity, I/O compatibility

Refactor history:
  2026-04-16: Split into gis_recommend/evaluation/{sampling, reranker_pipeline,
              diagnostics, report}.py. This file is the CLI + main orchestration only.
  2026-04-17: Moved from scripts/evaluate_system.py into the package proper.
              Entry points:
                - python -m gis_recommend.evaluation
                - python -m gis_recommend.evaluation.runner
                - gis-evaluate (via pyproject.toml [project.scripts])

Usage:
    python -m gis_recommend.evaluation --skip-qgis
    python -m gis_recommend.evaluation --eval-mode smoke --skip-qgis
    python -m gis_recommend.evaluation --skip-qgis --set-prior-mode off
    python -m gis_recommend.evaluation --skip-qgis --set-prior-mode soft \\
        --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth
    python -m gis_recommend.evaluation --samples 50 --skip-qgis    # quick run
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import defaultdict

import torch
from tqdm import tqdm

from gis_recommend.config.transformer_config import (
    OUTPUT_DIR, V4_LABELED_WORKFLOWS_PATH,
    VOCAB_SIZE, TOTAL_VOCAB_SIZE,
    L3_EMBEDDINGS_PATH as CONFIG_L3_EMBEDDINGS_PATH,
    CLASSIFICATION_HIERARCHY,
    ID_MAPPINGS_PATH as CONFIG_ID_MAPPINGS_PATH,
    SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
    SET_PREDICTOR_CONFIDENCE_THRESHOLD,
)
from gis_recommend.evaluation.semantic_metrics import (
    SemanticMetricsCalculator, SeqMetrics,
    compute_chain_metrics,
)
from gis_recommend.evaluation.sampling import (
    resolve_eval_max_samples, build_test_set,
)
from gis_recommend.evaluation.reranker_pipeline import (
    tokens_to_l3_codes,
    build_reranker_candidate_pool, build_reranker_candidate_pool_v3,
    run_l3_inference, run_qgis_evaluation,
)
from gis_recommend.evaluation.diagnostics import (
    compute_oracle_analysis,
    summarize_reranker_diagnostics, print_reranker_diagnostics,
    summarize_repair_diagnostics, print_repair_diagnostics,
    compute_executable_ratio, print_executable_ratio, load_io_types,
)
from gis_recommend.evaluation.report import (
    resolve_report_output_paths, write_json_report,
    print_report, build_report_json,
)
from gis_recommend.evaluation.run_contract import build_mainline_run_contract
from gis_recommend.evaluation.shadow_phase import build_retrieval_shadow_pool
from gis_recommend.config.consistency import (
    check_runtime_consistency, consistency_report_lines,
)

SEED = 42
L3_EMBEDDINGS_PATH = CONFIG_L3_EMBEDDINGS_PATH
HIERARCHY_CSV_PATH = CLASSIFICATION_HIERARCHY
ID_MAPPINGS_PATH = CONFIG_ID_MAPPINGS_PATH
TEST_SET_PATH = OUTPUT_DIR / "evaluation_test_set.json"


# ═════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        prog="gis-evaluate",
        description="Evaluate GIS recommendation system",
    )
    parser.add_argument("--eval-mode", choices=["smoke", "dev", "full"], default="dev",
                        help="Evaluation scale: smoke=200, dev=1000, full=all test samples (default: dev)")
    parser.add_argument("--samples", type=int, default=None,
                        help="Explicit stratified subsample size (overrides --eval-mode)")
    parser.add_argument("--skip-qgis", action="store_true",
                        help="Skip QGIS chain evaluation (no Neo4j needed)")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to transformer checkpoint (default: V4.6 best)")
    parser.add_argument("--sp-checkpoint", type=str, default=None,
                        help="Path to set predictor checkpoint (default: config dir)")
    parser.add_argument("--report-out", type=str, default=None,
                        help="Write an additional full report JSON to this exact path")
    parser.add_argument("--report-tag", type=str, default=None,
                        help="Optional tag used in the timestamped archived report filename")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Override both soft prior threshold and hard confidence threshold")
    parser.add_argument("--no-topk", action="store_true",
                        help="Disable Top-K set prediction in hard mode, use threshold mode")
    parser.add_argument("--set-prior-mode", choices=["off", "soft", "hard"], default="soft",
                        help="Set predictor constraint mode: off=disabled, soft=bias, hard=mask (default: soft)")
    parser.add_argument("--oracle", action="store_true",
                        help="Compute oracle metrics: best possible from top-N candidates")
    parser.add_argument("--use-reranker", action="store_true",
                        help="Use structured reranker: generate N*M candidates, verify, rerank")
    parser.add_argument("--reranker-v3", action="store_true",
                        help="Use two-stage reranker v3 (query-aware semantic + structural)")
    parser.add_argument("--strict-encoder", action="store_true",
                        help="Fail hard if QueryChainEncoder model (sentence_transformers) is unavailable")
    parser.add_argument("--use-repair", action="store_true",
                        help="Generate report-only chain repair suggestions for reranker top-1 (requires Neo4j)")
    parser.add_argument("--io-types", type=str, default=None,
                        help="Path to QGIS I/O metadata JSON (default: outputs_v2/qgis_operator_io_types.json)")
    parser.add_argument("--allow-legacy-io-types", action="store_true",
                        help="Allow explicit fallback to legacy outputs/qgis_operator_io_types.json when v2 metadata is missing")
    parser.add_argument("--executable-check", action="store_true",
                        help="Compute executable_chain_ratio (Level 1, local, fast)")
    parser.add_argument("--executable-strict", action="store_true",
                        help="Also run Level 2 executable check via Neo4j ChainValidator "
                             "(requires --executable-check and a live Neo4j)")
    parser.add_argument("--retrieval-shadow-k", type=int, default=0,
                        help="Report-only lexical train-split retrieval shadow pool size (default: 0/off)")
    args = parser.parse_args()

    enable_shadow = args.retrieval_shadow_k > 0
    run_contract = build_mainline_run_contract(
        checkpoint_path=args.checkpoint,
        sp_checkpoint=args.sp_checkpoint,
        io_types_path=args.io_types,
        allow_legacy_io_types=args.allow_legacy_io_types,
        candidate_pool_enabled=enable_shadow,
        decision_core_mode="shadow" if enable_shadow else "off",
        retrieval_mode="shadow" if enable_shadow else "off",
    )

    effective_soft_threshold = float(args.threshold) if args.threshold is not None else float(SET_PREDICTOR_SOFT_PRIOR_THRESHOLD)
    effective_hard_threshold = float(args.threshold) if args.threshold is not None else float(SET_PREDICTOR_CONFIDENCE_THRESHOLD)

    # Override thresholds if specified
    if args.threshold is not None:
        import gis_recommend.config.transformer_config as cfg
        import gis_recommend.inference.infer_l3_candidates_v4 as infer_mod
        cfg.SET_PREDICTOR_CONFIDENCE_THRESHOLD = args.threshold
        cfg.SET_PREDICTOR_SOFT_PRIOR_THRESHOLD = args.threshold
        infer_mod.SET_PREDICTOR_CONFIDENCE_THRESHOLD = args.threshold
        infer_mod.SET_PREDICTOR_SOFT_PRIOR_THRESHOLD = args.threshold
        print(f"  [Override] Both soft/hard thresholds = {args.threshold}")

    random.seed(SEED)
    torch.manual_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    effective_max_samples = resolve_eval_max_samples(args.eval_mode, args.samples)

    print("=" * 70)
    print("  GIS Recommendation System Evaluation V3")
    print("=" * 70)
    print(f"  Device: {device}")
    print(f"  Eval mode: {args.eval_mode}")
    print(f"  Effective max samples: {'full' if effective_max_samples is None else effective_max_samples}")
    print(f"  Effective soft prior threshold: {effective_soft_threshold}")
    print(f"  Effective hard confidence threshold: {effective_hard_threshold}")
    print(f"  Token profile: {run_contract.token_profile.name}")
    print(f"  Retrieval shadow mode: {run_contract.retrieval_mode}")
    print(
        "  QGIS I/O metadata: "
        f"{run_contract.data_authority.qgis_io_types_path} "
        f"({run_contract.data_authority.qgis_io_types_status})"
    )

    # ── Runtime consistency (advisory / warn-only; never blocks selection) ──
    consistency_report = check_runtime_consistency(
        vocab_size=VOCAB_SIZE,
        total_vocab_size=TOTAL_VOCAB_SIZE,
        id_mappings_path=run_contract.data_authority.id_mappings_path,
        transition_matrix_path=OUTPUT_DIR / "transition_allowed_next.json",
    )
    _consistency_lines = consistency_report_lines(consistency_report)
    if _consistency_lines:
        print("  Runtime consistency: ISSUES (advisory, not blocking) —")
        for _line in _consistency_lines:
            print(f"    {_line}")
    else:
        print("  Runtime consistency: OK")

    # ── Load data ────────────────────────────────────────────────
    print("\n[1] Loading data ...")
    with open(V4_LABELED_WORKFLOWS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    workflows = raw["labeled_workflows"] if isinstance(raw, dict) and "labeled_workflows" in raw else raw
    print(f"  Loaded {len(workflows)} workflows")

    # ── Build test set ───────────────────────────────────────────
    print("\n[2] Building test set ...")
    test_set, coverage_info = build_test_set(workflows, max_samples=effective_max_samples)
    print(f"  Test samples: {len(test_set)}")
    print(f"  Task types included: {len(coverage_info['included'])}")
    print(f"  Task types excluded (<5 samples): {len(coverage_info['excluded'])}")

    with open(TEST_SET_PATH, "w", encoding="utf-8") as f:
        json.dump({"test_set": test_set, "coverage_info": coverage_info}, f,
                  ensure_ascii=False, indent=2)
    print(f"  Saved to {TEST_SET_PATH}")

    # ── L3 inference ─────────────────────────────────────────────
    print("\n[3] Running L3 inference (beam search, deterministic) ...")
    t0 = time.time()
    l3_results, infer_meta = run_l3_inference(
        test_set, device, checkpoint_path=args.checkpoint,
        disable_topk=args.no_topk, set_prior_mode=args.set_prior_mode,
        sp_checkpoint=args.sp_checkpoint,
    )
    t_infer = time.time() - t0
    print(f"  Done in {t_infer:.0f}s")

    if args.retrieval_shadow_k > 0:
        print(f"\n[3a] Building retrieval shadow pools (train split only, top_k={args.retrieval_shadow_k}) ...")
        with open(run_contract.data_authority.split_path, "r", encoding="utf-8") as f:
            splits = json.load(f)
        train_indices = splits.get("train_indices", [])
        for sample, l3_res in zip(test_set, l3_results):
            l3_res["retrieval_shadow_pool"] = build_retrieval_shadow_pool(
                sample,
                workflows,
                train_indices,
                top_k=args.retrieval_shadow_k,
                contract=run_contract,
            )

    # ── Compute L3 metrics ───────────────────────────────────────
    print("\n[4] Computing L3 sequence metrics ...")

    with open(ID_MAPPINGS_PATH, "r", encoding="utf-8") as f:
        id_mappings = json.load(f)
    l3_map = id_mappings.get("l3", {})
    id_to_l3_code = {int(v): k for k, v in l3_map.items()}

    calc = SemanticMetricsCalculator(
        l3_embeddings_path=L3_EMBEDDINGS_PATH,
        hierarchy_csv_path=HIERARCHY_CSV_PATH,
        id_to_l3_code=id_to_l3_code,
        token_profile=run_contract.token_profile,
    )

    # ── Reranker: 多候选池 → 结构化重排序 ──────────────────────
    reranker_set_threshold = None
    reranker_encoder_status = None
    if args.use_reranker:
        print("\n[4a] Running reranker pipeline (N×M candidate pool) ...")
        from gis_recommend.operators.qgis_candidate_generator import QGISCandidateGenerator
        from gis_recommend.reranking import CandidateVerifier, StructuredReranker

        qgis_gen = QGISCandidateGenerator(
            beam_width=3,
            max_unknown_ratio=0.5,
            max_unknown_count=5,
            run_contract=run_contract,
            verbose=False,
        )
        verifier = CandidateVerifier(run_contract=run_contract)

        if args.reranker_v3:
            from gis_recommend.reranking import TwoStageReranker, QueryChainEncoder
            query_encoder = QueryChainEncoder(
                hierarchy_csv_path=HIERARCHY_CSV_PATH,
                id_to_l3_code=id_to_l3_code,
            )
            encoder_ok = query_encoder.probe()
            reranker_encoder_status = query_encoder.status()
            if not encoder_ok:
                msg = (
                    f"QueryChainEncoder unavailable — query_chain_sim will be 0 for all candidates. "
                    f"Reason: {reranker_encoder_status.get('load_error')}"
                )
                if args.strict_encoder:
                    raise RuntimeError(
                        "[FATAL] " + msg +
                        "\n  Install: pip install sentence-transformers"
                    )
                print(f"  [WARN] {msg}")
                print(f"  [WARN] v3 semantic signal is DISABLED. Results are NOT comparable to a full v3 run.")
            else:
                print(f"  [OK] QueryChainEncoder loaded ({reranker_encoder_status['model_name']})")
            reranker = TwoStageReranker(verifier, query_encoder=query_encoder)
            _effective_mode = infer_meta.get("effective_set_prior_mode", "soft")
            reranker_set_threshold = (
                effective_hard_threshold if _effective_mode == "hard"
                else effective_soft_threshold
            )
            print(f"  [OK] Two-stage reranker v3 (semantic) initialized, set_threshold={reranker_set_threshold:.2f} ({_effective_mode})")
        else:
            reranker = StructuredReranker(verifier)

        reranked_count = 0
        sample_pairs = zip(test_set, l3_results)
        for sample, l3_res in tqdm(sample_pairs, total=len(test_set), desc="Reranker", unit="sample"):
            all_l3_cands = l3_res.get("all_candidates", [])
            if not all_l3_cands:
                continue

            l3_top1_score = all_l3_cands[0].final_score if all_l3_cands else 0.0

            if args.reranker_v3:
                pool_qgis, pool_l3, beam_ranks = build_reranker_candidate_pool_v3(
                    all_l3_cands,
                    id_to_l3_code,
                    qgis_gen,
                    per_l3_top_k=3,
                )
                if not pool_qgis:
                    continue
                result = reranker.rerank(
                    pool_qgis, pool_l3,
                    expected_length=l3_res.get("expected_length", 8),
                    set_predictor_tokens=l3_res.get("set_predictor_tokens"),
                    task_description=sample.get("task_description", ""),
                    l3_top1_score=l3_top1_score,
                    beam_ranks=beam_ranks,
                    set_threshold=reranker_set_threshold,
                )
            else:
                pool_qgis, pool_l3 = build_reranker_candidate_pool(
                    all_l3_cands,
                    id_to_l3_code,
                    qgis_gen,
                    per_l3_top_k=3,
                )
                if not pool_qgis:
                    continue
                result = reranker.rerank(
                    pool_qgis, pool_l3,
                    expected_length=l3_res.get("expected_length", 8),
                    set_predictor_tokens=l3_res.get("set_predictor_tokens"),
                )

            if result.best_candidate is not None and result.best_l3_candidate is not None:
                best_l3_cand = result.best_l3_candidate
                l3_res["pred_tokens"] = best_l3_cand.tokens
                l3_res["pred_codes"] = tokens_to_l3_codes(best_l3_cand.tokens, id_to_l3_code)
                l3_res["pred_score"] = best_l3_cand.final_score
                l3_res["pred_l3_score"] = best_l3_cand.final_score
                l3_res["reranker_score"] = result.best_features.final_score
                l3_res["reranker_pool_size"] = len(pool_qgis)
                l3_res["reranker_features"] = result.best_features.to_dict()
                l3_res["selected_qgis_candidate"] = result.best_candidate
                l3_res["selected_qgis_chain"] = list(result.best_candidate.qgis_sequence)
                l3_res["qgis_score_components"] = dict(getattr(result.best_candidate, "score_components", {}))
                l3_res["selected_from_reranker"] = True
                reranked_count += 1

                l3_res["reranker_pool_qgis"] = pool_qgis
                l3_res["reranker_pool_l3"] = pool_l3

        print(f"  Reranked {reranked_count}/{len(test_set)} samples")

    # ── Repair: 对 reranker top-1 做链修复（需要 Neo4j）─────────
    repair_stats = None
    if args.use_repair and args.use_reranker:
        print("\n[4a-repair] Applying chain repair to reranker top-1 ...")
        try:
            from gis_recommend.knowledge_graph.neo4j_graphrag_retriever import Neo4jGraphRAGRetriever
            from gis_recommend.knowledge_graph.chain_validator import ChainValidator
            from gis_recommend.knowledge_graph.chain_repair import ChainRepairer

            retriever = Neo4jGraphRAGRetriever()
            validator = ChainValidator(retriever)
            io_types_path = run_contract.data_authority.qgis_io_types_path
            io_types = {}
            if io_types_path.exists():
                with open(io_types_path, "r", encoding="utf-8") as f:
                    io_types = json.load(f).get("operators", {})

            repairer = ChainRepairer(retriever, validator, llm_scorer=None, io_types=io_types)

            suggested_count = 0
            for l3_res in l3_results:
                qgis_cand = l3_res.get("selected_qgis_candidate")
                if qgis_cand is None:
                    continue
                chain = qgis_cand.qgis_sequence
                val_result = validator.validate_chain(chain)
                if val_result.issues:
                    l3_res["repair_attempted"] = True
                    before_metrics = compute_chain_metrics(chain, val_result).to_dict()
                    repaired_cand, _final_val, repair_log = repairer.repair(
                        qgis_cand, val_result, user_query="", max_rounds=2
                    )
                    suggested_chain = list(repaired_cand.qgis_sequence)
                    if repair_log:
                        first_suggestion = repair_log[0].get("suggested_chain")
                        if isinstance(first_suggestion, list) and first_suggestion:
                            suggested_chain = list(first_suggestion)
                    suggested_validation = validator.validate_chain(suggested_chain)
                    after_metrics = compute_chain_metrics(suggested_chain, suggested_validation).to_dict()
                    suggested = len(suggested_validation.issues) < len(val_result.issues)
                    if suggested:
                        suggested_count += 1
                    l3_res["repair_diagnostics"] = {
                        "changed_chain": False,
                        "suggested_changed_chain": list(suggested_chain) != list(chain),
                        "suggested_issue_reduction": suggested,
                        "before_issue_len": len(val_result.issues),
                        "after_issue_len": len(suggested_validation.issues),
                        "before": before_metrics,
                        "after": after_metrics,
                    }
                    l3_res["repair_suggested"] = suggested
                    l3_res["repair_candidate_chain"] = list(suggested_chain)
                    l3_res["repair_applied"] = False
                    l3_res["repair_log"] = [str(entry) for entry in repair_log]

            repair_stats = {"suggested": suggested_count, "applied": 0, "total": len(test_set)}
            print(f"  Repair suggestions {suggested_count}/{len(test_set)} samples (applied=0)")

            try:
                retriever.close()
            except Exception:
                pass
        except Exception as e:
            print(f"  [WARN] Repair failed (Neo4j required): {e}")
            repair_stats = {"error": str(e)}
    elif args.use_repair and not args.use_reranker:
        print("  [WARN] --use-repair requires --use-reranker, skipping")

    # ── Compute L3 metrics（用 rerank/repair 后的 pred_tokens）───
    print("\n[4b] Computing L3 sequence metrics ...")

    seq_metrics: list[SeqMetrics] = []
    for i, (sample, l3_res) in enumerate(zip(test_set, l3_results)):
        ref_tokens = sample["l3_sequence"]
        pred_tokens = l3_res["pred_tokens"]
        m = calc.compute(pred_tokens, ref_tokens)
        seq_metrics.append(m)

    agg = SemanticMetricsCalculator.aggregate(seq_metrics)

    reranker_diagnostics = None
    if args.use_reranker:
        reranker_diagnostics = summarize_reranker_diagnostics(test_set, l3_results, calc)
        print_reranker_diagnostics(reranker_diagnostics)

    repair_diagnostics = None
    if args.use_repair and args.use_reranker:
        repair_diagnostics = summarize_repair_diagnostics(test_set, l3_results)
        print_repair_diagnostics(repair_diagnostics)

    # ── Oracle Analysis ─────────────────────────────────────────
    oracle_results = None
    if args.oracle:
        print("\n[4b] Computing oracle metrics (best from top-N candidates) ...")
        current_label = "reranked" if args.use_reranker else "top-1"
        oracle_results = compute_oracle_analysis(
            test_set=test_set,
            l3_results=l3_results,
            calc=calc,
            current_agg=agg,
            current_label=current_label,
        )

        print(f"\n{'='*70}")
        print(f"  Oracle Analysis (max {oracle_results['max_k']} candidates per sample)")
        print(f"{'='*70}")
        print(f"  {'Label':>8} | {'Set F1':>8} | {'gap':>8} | {'LCS':>8} | {'gap':>8} | {'LenRatio':>9} | {'gap':>8}")
        print(f"  {'-'*65}")
        for row in oracle_results["rows"]:
            print(
                f"  {row['label']:>8} | {row['set_f1']*100:>7.2f}% | {row['gap_set_f1']*100:>+7.2f}% | "
                f"{row['lcs_ratio']:>8.4f} | {row['gap_lcs_ratio']:>+8.4f} | "
                f"{row['length_ratio']:>9.4f} | {row['gap_length_ratio']:>+8.4f}"
            )

        if args.use_reranker:
            print(f"\n  QGIS Pool Oracle (reranker candidate pool):")
            pool_oracle_metrics = []
            for sample, l3_res in zip(test_set, l3_results):
                ref_tokens = sample["l3_sequence"]
                pool_l3_cands = l3_res.get("reranker_pool_l3", [])
                if not pool_l3_cands:
                    pool_oracle_metrics.append(calc.compute(l3_res.get("pred_tokens", []), ref_tokens))
                    continue
                best_m = None
                best_s = -1.0
                for l3_cand in pool_l3_cands:
                    m = calc.compute(l3_cand.tokens, ref_tokens)
                    len_s = max(0.0, 1.0 - abs(1.0 - m.length_ratio))
                    s = 0.5 * m.set_f1 + 0.3 * m.lcs_ratio + 0.2 * len_s
                    if s > best_s:
                        best_s = s
                        best_m = m
                pool_oracle_metrics.append(best_m)
            pool_oracle_agg = calc.aggregate(pool_oracle_metrics)
            gap_f1 = pool_oracle_agg.set_f1 - agg.set_f1
            gap_lcs = pool_oracle_agg.lcs_ratio - agg.lcs_ratio
            print(f"  pool oracle Set F1: {pool_oracle_agg.set_f1*100:.2f}% (gap: {gap_f1*100:+.2f}%)")
            print(f"  pool oracle LCS:    {pool_oracle_agg.lcs_ratio:.4f} (gap: {gap_lcs:+.4f})")
            if oracle_results:
                oracle_results["qgis_pool_oracle"] = pool_oracle_agg.to_dict()

    # Per-task-type breakdown
    by_type: dict = defaultdict(lambda: {
        "n": 0, "set_f1": 0, "soft_set_sim": 0, "l2_set_f1": 0, "l2_accuracy": 0,
        "lcs_ratio": 0, "token_accuracy": 0, "sequence_em": 0, "length_ratio": 0,
        "coverage": 0, "validity": 0, "existence_validity": 0, "structural_validity": 0,
        "io_compatibility": 0,
    })
    for sample, m in zip(test_set, seq_metrics):
        tt = sample["task_type"]
        d = by_type[tt]
        d["n"] += 1
        for key in ["set_f1", "soft_set_sim", "l2_set_f1", "l2_accuracy", "lcs_ratio",
                     "token_accuracy", "length_ratio"]:
            d[key] += getattr(m, key)
        d["sequence_em"] += int(m.sequence_em)

    for tt, d in by_type.items():
        n = d["n"]
        for key in ["set_f1", "soft_set_sim", "l2_set_f1", "l2_accuracy", "lcs_ratio",
                     "token_accuracy", "sequence_em", "length_ratio"]:
            d[key] = d[key] / n if n > 0 else 0

    # ── QGIS evaluation ─────────────────────────────────────────
    chain_results = None
    if not args.skip_qgis:
        print("\n[5] Running QGIS chain evaluation ...")
        t0 = time.time()
        chain_results = run_qgis_evaluation(test_set, l3_results, run_contract=run_contract)
        t_qgis = time.time() - t0
        print(f"  Done in {t_qgis:.0f}s")

        # Back-fill the QGIS chain into l3_results so downstream diagnostics
        # (e.g. compute_executable_ratio) can find it even in baseline runs
        # that don't use the reranker.
        for l3_res, cr in zip(l3_results, chain_results):
            if l3_res.get("selected_qgis_chain") is None and cr.get("qgis_chain"):
                l3_res["qgis_chain"] = cr["qgis_chain"]

        type_chains: dict = defaultdict(list)
        for sample, cr in zip(test_set, chain_results):
            if cr.get("total_steps", 0) > 0:
                type_chains[sample["task_type"]].append(cr)

        for tt, chains in type_chains.items():
            d = by_type[tt]
            d["coverage"] = sum(c["coverage"] for c in chains) / len(chains)
            d["validity"] = sum(c["validity"] for c in chains) / len(chains)
            d["existence_validity"] = sum(c.get("existence_validity", c["validity"]) for c in chains) / len(chains)
            d["structural_validity"] = sum(c.get("structural_validity", c["validity"]) for c in chains) / len(chains)
            d["io_compatibility"] = sum(c["io_compatibility"] for c in chains) / len(chains)
    else:
        print("\n[5] Skipping QGIS evaluation (--skip-qgis)")

    # ── Executable Chain Analysis ───────────────────────────────
    # Level 1: local io_types (always runs if file exists, very fast)
    # Level 2: Neo4j ChainValidator (only if --executable-strict, needs Neo4j)
    executable_diag = None
    if args.executable_check:
        # Warn about combinations that guarantee empty input:
        #   - --skip-qgis without --use-reranker: no chain source at all
        if args.skip_qgis and not args.use_reranker:
            print(
                "\n  [WARN] --executable-check with --skip-qgis and without "
                "--use-reranker: no QGIS chains will be available. "
                "All ratios will be reported as N/A."
            )

        print("\n[5b] Computing executable-chain ratio ...")
        io_types = load_io_types(run_contract.data_authority.qgis_io_types_path)
        level2_validator = None
        if args.executable_strict:
            try:
                from gis_recommend.knowledge_graph.neo4j_graphrag_retriever import Neo4jGraphRAGRetriever
                from gis_recommend.knowledge_graph.chain_validator import ChainValidator
                _retriever = Neo4jGraphRAGRetriever()
                level2_validator = ChainValidator(_retriever)
                print("  [OK] Neo4j validator ready for Level 2 check")
            except Exception as e:
                print(f"  [WARN] Level 2 Neo4j validator failed to init: {e}")
                print(f"  [WARN] Falling back to Level 1 only")

        executable_diag = compute_executable_ratio(
            test_set, l3_results,
            io_types=io_types,
            validator=level2_validator,
        )
        print_executable_ratio(executable_diag)

        if level2_validator is not None:
            try:
                level2_validator.retriever.close()
            except Exception:
                pass

    # ── Report ───────────────────────────────────────────────────
    print_report(test_set, seq_metrics, agg, chain_results, dict(by_type))

    report = build_report_json(
        test_set, seq_metrics, agg, l3_results, chain_results,
        dict(by_type), coverage_info, reranker_diagnostics=reranker_diagnostics,
        repair_diagnostics=repair_diagnostics,
        run_contract=run_contract,
    )
    if executable_diag is not None:
        report["executable_diagnostics"] = executable_diag
    report["eval_version"] = "v3"
    report["experiment_meta"] = {
        "checkpoint": infer_meta["transformer_checkpoint"],
        "sp_checkpoint": infer_meta["set_predictor_checkpoint"],
        "set_prior_mode": infer_meta["requested_set_prior_mode"],
        "effective_set_prior_mode": infer_meta["effective_set_prior_mode"],
        "set_predictor_loaded": infer_meta["set_predictor_loaded"],
        "set_predictor_use_rich_cross_attn": infer_meta["set_predictor_use_rich_cross_attn"],
        "set_predictor_num_active_tokens": infer_meta["set_predictor_num_active_tokens"],
        "use_topk_set_prediction": infer_meta["use_topk_set_prediction"],
        "soft_prior_threshold": effective_soft_threshold,
        "hard_confidence_threshold": effective_hard_threshold,
        "threshold_override": args.threshold,
        "no_topk": args.no_topk,
        "eval_mode": args.eval_mode,
        "samples": args.samples,
        "effective_max_samples": effective_max_samples,
        "oracle": args.oracle,
        "use_reranker": args.use_reranker,
        "reranker_v3": args.reranker_v3,
        "reranker_set_threshold": reranker_set_threshold if args.reranker_v3 else None,
        "reranker_encoder_status": reranker_encoder_status if args.reranker_v3 else None,
        "strict_encoder": args.strict_encoder,
        "use_repair": args.use_repair,
        "executable_check": args.executable_check,
        "executable_strict": args.executable_strict,
        "io_types": str(run_contract.data_authority.qgis_io_types_path),
        "allow_legacy_io_types": args.allow_legacy_io_types,
        "io_metadata_profile": run_contract.data_authority.io_metadata_profile,
        "token_profile": run_contract.token_profile.to_dict(),
        "system_lineage": run_contract.system_lineage,
        "mainline_eligible": run_contract.mainline_eligible,
        "report_out": args.report_out,
        "report_tag": args.report_tag,
    }
    report["experiment_meta"]["runtime_consistency"] = {
        "ok": consistency_report.ok,
        "issues": [
            {"code": i.code, "severity": i.severity, "message": i.message}
            for i in consistency_report.issues
        ],
    }
    if oracle_results:
        report["oracle_analysis"] = oracle_results["by_k"]
        report["oracle_rows"] = oracle_results["rows"]
        if "qgis_pool_oracle" in oracle_results:
            report["qgis_pool_oracle"] = oracle_results["qgis_pool_oracle"]
    if repair_stats:
        report["repair_stats"] = repair_stats
    report_paths = resolve_report_output_paths(args.report_out, report_tag=args.report_tag)
    report["experiment_meta"]["report_paths"] = [str(path) for path in report_paths]
    for output_path in report_paths:
        write_json_report(report, output_path)
    print("")
    for output_path in report_paths:
        print(f"  Full report saved to {output_path}")


if __name__ == "__main__":
    main()
