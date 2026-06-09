#!/usr/bin/env python3
"""Evaluate ExecutionAwareSelector against retrieval-only and beam-only baselines.

Answers the question:
    Can a rule-based execution-aware selector pick a better candidate from
    a multi-source pool than either retrieval top-1 or Transformer beam top-1?

Outputs: outputs_v2/diagnostics/execution_aware_selector/
    selector_report.json   — full per-sample metrics and traces
    selector_report.md     — human-readable summary
    selected_candidates.csv — top-1 selection per sample with feature breakdown

Usage:
    python scripts/evaluate_execution_aware_selector.py                    # retrieval only
    python scripts/evaluate_execution_aware_selector.py --use-beam          # + Transformer beam
    python scripts/evaluate_execution_aware_selector.py --num-samples 100   # subset
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch
from tqdm import tqdm

from gis_recommend.config.transformer_config import (
    DEVICE, OUTPUT_DIR, TOTAL_VOCAB_SIZE, VOCAB_SIZE,
    V4_QG_LABELED_WORKFLOWS_PATH, V4_QG_SPLITS_PATH, V4_QG_TASK_TYPE_VOCAB_PATH,
    V4_6_QG_TRANSFORMER_CHECKPOINT_DIR, V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR,
    L3_EMBEDDINGS_PATH, CLASSIFICATION_HIERARCHY, ID_MAPPINGS_PATH,
    SPECIAL_TOKENS,
)
from gis_recommend.planning import ExecutionAwareSelector, SelectionResult
from gis_recommend.training.train_v4_2 import count_invalid_transitions

try:
    from scripts.evaluate_workflow_usability import (
        UsabilityEvaluator,
        build_commutative_pairs,
        build_qgis_mapping,
        build_token_roles,
        compute_critical_operators,
    )
except ModuleNotFoundError:
    from evaluate_workflow_usability import (
        UsabilityEvaluator,
        build_commutative_pairs,
        build_qgis_mapping,
        build_token_roles,
        compute_critical_operators,
    )

SCHEMA_VERSION = "gis_recommend.planning.execution_aware_selector.eval.v1"
SP_TOKEN_IDS = {-1, -2, -3, -4}
OUTPUT_DIR_PATH = OUTPUT_DIR / "diagnostics" / "execution_aware_selector"


# ═══════════════════════════════════════════════════════════════════════
# Data loading (reuse same patterns as evaluate_workflow_usability.py)
# ═══════════════════════════════════════════════════════════════════════

def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    return payload.get("labeled_workflows", payload)


def _load_csv(path: Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return [int(t) for t in tokens if int(t) not in SP_TOKEN_IDS]


def _quality_penalty(
    tokens: Sequence[int],
    warnings: Sequence[str] | None = None,
    token_names: dict[int, str] | None = None,
) -> float:
    """Penalty for usable-but-low-quality chains.

    This is intentionally conservative: usability remains the primary gate, while
    repeated operators and non-blocking evaluator warnings break ties inside the
    usable beam set.
    """
    toks = [int(t) for t in tokens]
    warnings = list(warnings or [])

    duplicate_extra = max(0, len(toks) - len(set(toks)))
    consecutive_duplicates = sum(
        1 for i in range(max(len(toks) - 1, 0)) if toks[i] == toks[i + 1]
    )

    penalty = 0.0
    penalty += min(0.30, 0.08 * duplicate_extra)
    penalty += min(0.35, 0.15 * consecutive_duplicates)

    if token_names:
        names = [str(token_names.get(t, "")) for t in toks]
        loop_count = _train_apply_cycle_count(names)
        penalty += min(0.45, 0.25 * loop_count)

    warning_penalties = {
        "FP04:consecutive_duplicate": 0.25,
        "consecutive_duplicate": 0.25,
        "FP02:export_before_processing": 0.20,
        "export_before_processing": 0.20,
        "harmful_steps": 0.20,
        "missing_critical_steps": 0.12,
        "length_anomaly": 0.08,
        "FP05:length_anomaly": 0.08,
    }
    for warning in warnings:
        for marker, value in warning_penalties.items():
            if marker in str(warning):
                penalty += value
                break

    return min(1.0, penalty)


def _quality_adjusted_score(
    usability_score: float,
    tokens: Sequence[int],
    warnings: Sequence[str] | None = None,
    token_names: dict[int, str] | None = None,
) -> float:
    return float(usability_score) - _quality_penalty(tokens, warnings, token_names)


def _is_train_operator_name(name: str) -> bool:
    text = str(name).lower()
    return "train" in text


def _is_apply_operator_name(name: str) -> bool:
    text = str(name).lower()
    return "apply" in text


def _train_apply_cycle_count(names: Sequence[str]) -> int:
    count = 0
    for i in range(max(len(names) - 2, 0)):
        a, b, c = names[i:i + 3]
        if (
            _is_train_operator_name(a)
            and _is_apply_operator_name(b)
            and _is_train_operator_name(c)
        ) or (
            _is_apply_operator_name(a)
            and _is_train_operator_name(b)
            and _is_apply_operator_name(c)
        ):
            count += 1
    return count


def _task_type(wf: dict) -> str:
    tm = wf.get("task_metadata", {}) or {}
    return str(tm.get("task_type_normalized", tm.get("task_type", "Unknown")))


def _task_text(wf: dict) -> str:
    tm = wf.get("task_metadata", {}) or {}
    return " ".join(
        p for p in [
            str(tm.get("task_name", "")),
            str(tm.get("task_description", "")),
        ] if p
    ).strip()


def _tokenize(text: str) -> set[str]:
    tokens = set()
    for t in re.findall(r"[A-Za-z0-9_]+", str(text).lower()):
        if len(t) > 1:
            tokens.add(t)
    return tokens


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ═══════════════════════════════════════════════════════════════════════
# Retrieval (minimal, same logic as LexicalRetrieval in usability eval)
# ═══════════════════════════════════════════════════════════════════════

class MiniRetrieval:
    def __init__(self, train_wf: list[dict]):
        self.by_task: dict[str, list[dict]] = defaultdict(list)
        self.by_task_text: dict[str, list[set[str]]] = defaultdict(list)
        for wf in train_wf:
            task = _task_type(wf)
            self.by_task[task].append(wf)
            self.by_task_text[task].append(_tokenize(_task_text(wf)))

    def retrieve(self, task_type: str, query_text: str, k: int = 10) -> list[dict]:
        pool = self.by_task.get(task_type, [])
        pool_texts = self.by_task_text.get(task_type, [])
        query_tokens = _tokenize(query_text or task_type)
        seen = set()
        scored = []
        for idx, wf in enumerate(pool):
            seq = tuple(_content_tokens(wf.get("l3_sequence", [])))
            if not seq or seq in seen:
                continue
            seen.add(seq)
            wf_tokens = pool_texts[idx] if idx < len(pool_texts) else set()
            score = _jaccard(query_tokens, wf_tokens)
            scored.append({"tokens": list(seq), "rank": idx, "score": score})
        scored.sort(key=lambda r: (-r["score"], r["rank"], len(r["tokens"])))
        return scored[:k]


# ═══════════════════════════════════════════════════════════════════════
# Usability helper for lightweight unit tests and transition diagnostics.
# ═══════════════════════════════════════════════════════════════════════

def check_usable(
    tokens: list[int],
    token_to_qgis: dict[int, list[str]],
    token_roles: dict[int, dict],
    transition_mask: dict[int, set[int]],
    critical_operators: dict[str, set[int]],
    task_type: str,
    expected_length: int = 8,
) -> tuple[bool, list[str]]:
    n = len(tokens)
    failures: list[str] = []

    if n == 0:
        return False, ["empty_chain"]

    # FP02: export before processing
    export_seen = False
    has_after_export = False
    for i, t in enumerate(tokens):
        role = token_roles.get(t, {})
        if role.get("is_export"):
            export_seen = True
        elif export_seen:
            has_after_export = True
    if export_seen and has_after_export:
        failures.append("FP02_export_before_processing")

    # FP04: consecutive duplicates
    for i in range(1, n):
        if tokens[i] == tokens[i - 1]:
            failures.append("FP04_consecutive_duplicate")
            break

    # Low QGIS mapping
    mapped = sum(1 for t in tokens if t in token_to_qgis)
    if mapped / max(n, 1) < 0.3:
        failures.append("low_qgis_mapping")

    # Illegal transitions
    if transition_mask and n >= 2:
        violations, total = count_invalid_transitions(tokens, transition_mask)
        if total > 0 and violations / total > 0.3:
            failures.append("illegal_transitions")

    # Length anomaly
    if n < max(2, expected_length // 3):
        failures.append("too_short")
    if n > expected_length * 3:
        failures.append("too_long")

    # Critical operator coverage
    crits = critical_operators.get(task_type, set())
    if crits:
        covered = sum(1 for t in tokens if t in crits)
        if covered / len(crits) < 0.3:
            failures.append("low_critical_coverage")

    return len(failures) == 0, failures


def compute_usable_rate(results: list[dict]) -> float:
    n = len(results)
    if n == 0:
        return 0.0
    return sum(1 for r in results if r.get("usable", False)) / n


def _l3_codes_from_tokens(tokens: Sequence[int], id_to_code: dict[int, str]) -> list[str]:
    return [
        id_to_code[int(t)]
        for t in tokens
        if int(t) in id_to_code
    ]


def _build_qgis_landing_record(
    *,
    retriever,
    evaluator,
    task_text: str,
    final_tokens: Sequence[int],
    id_to_code: dict[int, str],
    k: int = 5,
) -> dict:
    """Build shadow QGIS landing diagnostics for a selected L3 chain."""
    l3_codes = _l3_codes_from_tokens(final_tokens, id_to_code)
    candidates = retriever.retrieve(
        task_text=task_text,
        l3_codes=l3_codes,
        prefer_vector=False,
        prefer_raster=False,
        prefer_mixed=False,
        k=k,
        evaluator=evaluator,
    )

    topk = []
    for cand in candidates:
        ev = evaluator.evaluate(cand.qgis_ops)
        topk.append({
            "qgis_ops": list(cand.qgis_ops),
            "score": round(float(cand.score), 6),
            "quality": round(float(ev.quality_score), 6),
            "is_valid": bool(ev.is_valid),
            "flags": list(ev.flags),
            "l3_sequence": list(cand.l3_sequence or []),
            "score_components": dict(getattr(cand, "score_components", {}) or {}),
        })

    top1 = topk[0] if topk else {}
    top1_ops = list(top1.get("qgis_ops", []))
    native_bridge_ops = {"native:reprojectlayer", "qgis:reprojectlayer"}
    native_bridge_hit = any(str(op).lower() in native_bridge_ops for op in top1_ops)
    l3_bridge_hit = bool(top1.get("l3_sequence"))

    return {
        "enabled": True,
        "l3_codes": l3_codes,
        "top1_chain": top1_ops,
        "top1_score": top1.get("score", 0.0),
        "top1_quality": top1.get("quality", 0.0),
        "top1_valid": bool(top1.get("is_valid", False)),
        "top1_flags": list(top1.get("flags", [])),
        "top1_l3_sequence": list(top1.get("l3_sequence", [])),
        "top1_score_components": dict(top1.get("score_components", {})),
        "l3_bridge_hit": l3_bridge_hit,
        "native_bridge_hit": native_bridge_hit,
        "combined_bridge_hit": bool(l3_bridge_hit or native_bridge_hit),
        "topk": topk,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main evaluation
# ═══════════════════════════════════════════════════════════════════════

def build_selector_artifacts(
    data_path: Path,
    splits_path: Path,
    hierarchy_path: Path,
    id_mappings_path: Path,
    io_types_path: Path,
    transition_path: Path,
    length_stats_path: Path,
) -> dict:
    """Load all metadata needed to construct ExecutionAwareSelector."""
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    hierarchy = _load_csv(hierarchy_path)
    id_mappings = _load_json(id_mappings_path)

    # code → token id
    l3_map = id_mappings.get("l3", {})
    code_to_id = {k: int(v) for k, v in l3_map.items()}
    id_to_code = {int(v): str(k) for k, v in code_to_id.items()}

    # token → qgis operators
    token_to_qgis = build_qgis_mapping(id_mappings, code_to_id)

    # I/O types
    io_types = {}
    if io_types_path.exists():
        io_types = _load_json(io_types_path)

    # Transition matrix
    transition_mask: dict[int, set[int]] = {}
    if transition_path.exists():
        tdata = _load_json(transition_path)
        for a_str, nxt in tdata.get("allowed_next", {}).items():
            allowed = {int(b) for b in nxt.keys()}
            if allowed:
                transition_mask[int(a_str)] = allowed

    # Token roles
    token_roles = build_token_roles(hierarchy, code_to_id)
    token_names = {
        int(code_to_id[row.get("l3_code", "")]): row.get("l3_name", "")
        for row in hierarchy
        if row.get("l3_code", "") in code_to_id
    }

    # Length stats
    length_stats = {}
    if length_stats_path.exists():
        length_stats = _load_json(length_stats_path)

    # Commutative pairs
    commutative_pairs = build_commutative_pairs(workflows)

    # Critical operators
    critical_operators = compute_critical_operators(workflows)

    train_indices = splits.get("train_indices", [])
    val_indices = splits.get("val_indices", [])
    test_indices = splits.get("test_indices", [])
    train_wf = [workflows[i] for i in train_indices]
    val_wf = [workflows[i] for i in val_indices]
    test_wf = [workflows[i] for i in test_indices]

    l3_vocab_path = id_mappings_path.with_name("l3_vocab_v2.json")
    usability_evaluator = UsabilityEvaluator(
        hierarchy_path=hierarchy_path,
        id_mappings_path=id_mappings_path,
        l3_vocab_path=l3_vocab_path,
        train_workflows=train_wf,
    )

    selector = ExecutionAwareSelector(
        token_to_qgis=token_to_qgis,
        io_types=io_types,
        transition_mask=transition_mask,
        token_roles=token_roles,
        length_stats=length_stats,
        commutative_pairs=commutative_pairs,
        critical_operators=critical_operators,
    )

    return {
        "selector": selector,
        "train_wf": train_wf,
        "val_wf": val_wf,
        "test_wf": test_wf,
        "split_indices": {
            "train": list(train_indices),
            "val": list(val_indices),
            "test": list(test_indices),
        },
        "token_to_qgis": token_to_qgis,
        "id_to_code": id_to_code,
        "token_roles": token_roles,
        "token_names": token_names,
        "transition_mask": transition_mask,
        "critical_operators": critical_operators,
        "length_stats": length_stats,
        "usability_evaluator": usability_evaluator,
        "selector_config": selector.to_dict(),
    }


def _select_workflow_split(
    workflows: list[dict],
    splits: dict,
    split: str,
) -> tuple[list[dict], list[int]]:
    """Return workflows and original dataset indices for a named split."""
    split_key = f"{split}_indices"
    if split_key not in splits:
        raise ValueError(f"Unknown split {split!r}; expected one of train, val, test")
    indices = [int(i) for i in splits.get(split_key, [])]
    selected = [workflows[i] for i in indices]
    return selected, indices


def evaluate(
    *,
    artifacts: dict,
    num_samples: int = 200,
    split: str = "test",
    use_beam: bool = False,
    checkpoint_path: Path | None = None,
    set_predictor_checkpoint_path: Path | None = None,
    retrieval_k: int = 10,
    selection_policy: str = "selector",
    use_qgis_landing: bool = False,
    qgis_landing_dataset_path: Path | None = None,
    qgis_landing_catalog_path: Path | None = None,
    qgis_landing_k: int = 5,
) -> dict:
    selector: ExecutionAwareSelector = artifacts["selector"]
    eval_wf: list[dict] = artifacts[f"{split}_wf"]
    split_indices: list[int] = artifacts["split_indices"].get(split, [])
    token_to_qgis = artifacts["token_to_qgis"]
    id_to_code = artifacts.get("id_to_code", {})
    token_roles = artifacts["token_roles"]
    token_names = artifacts.get("token_names", {})
    transition_mask = artifacts["transition_mask"]
    critical_operators = artifacts["critical_operators"]
    length_stats = artifacts["length_stats"]
    usability_evaluator: UsabilityEvaluator = artifacts["usability_evaluator"]

    retrieval = MiniRetrieval(artifacts["train_wf"])

    qgis_landing_retriever = None
    qgis_landing_evaluator = None
    if use_qgis_landing:
        from gis_recommend.planning.qgis_chain_planner import build_qgis_chain_planner
        qgis_landing_retriever, qgis_landing_evaluator = build_qgis_chain_planner(
            qgis_landing_dataset_path or (OUTPUT_DIR / "qgis_chain_dataset.jsonl"),
            qgis_landing_catalog_path or (ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"),
        )

    # Load beam inferencer if requested
    inferencer = None
    if use_beam and checkpoint_path and checkpoint_path.exists():
        from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4
        sp_path = set_predictor_checkpoint_path
        if sp_path is None:
            default_sp = V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
            sp_path = default_sp if default_sp.exists() else None
        elif not sp_path.exists():
            raise FileNotFoundError(f"Set Predictor checkpoint not found: {sp_path}")
        task_vocab_path = V4_QG_TASK_TYPE_VOCAB_PATH if V4_QG_TASK_TYPE_VOCAB_PATH.exists() else None
        inferencer = L3SequenceInferencerV4(
            checkpoint_path=checkpoint_path,
            device=DEVICE,
            set_predictor_path=sp_path,
            task_vocab_path=Path(str(task_vocab_path)) if task_vocab_path else None,
        )
        print(f"  Beam inferencer loaded: {checkpoint_path}")
        print(f"  Set Predictor: {sp_path if sp_path else 'disabled'}")
        if task_vocab_path:
            print(f"  Task vocab: {task_vocab_path} ({_load_json(Path(str(task_vocab_path))).get('num_types', '?')} types)")

    test_samples = eval_wf[:num_samples]
    test_sample_indices = split_indices[:num_samples]
    results = []
    source_win_counts: dict[str, int] = defaultdict(int)
    selector_win_count = 0
    baseline_best_count = 0
    final_source_counts: dict[str, int] = defaultdict(int)
    final_usable_source_counts: dict[str, int] = defaultdict(int)

    by_type = length_stats.get("by_task_type", {})
    global_median = length_stats.get("global_median", length_stats.get("median", 8))

    for local_idx, sample in enumerate(tqdm(test_samples, desc="Evaluating", unit="sample")):
        sample_index = int(test_sample_indices[local_idx]) if local_idx < len(test_sample_indices) else local_idx
        task_meta = sample.get("task_metadata", {}) or {}
        task_type = _task_type(sample)
        task_desc = _task_text(sample)
        ref_tokens = _content_tokens(sample.get("l3_sequence", []))
        expected_len = int(by_type.get(task_type, {}).get("median", global_median))

        # ── Retrieval candidates ──
        ret_candidates = retrieval.retrieve(task_type, task_desc, k=retrieval_k)

        # ── Beam candidates (optional) ──
        beam_candidates = []
        beam_error = None
        set_predictor_tokens = None
        if inferencer is not None:
            try:
                inferencer.set_complexity_profile(task_type)
                beam_cands = inferencer.infer(
                    task_name=sample.get("task_metadata", {}).get("task_name", ""),
                    task_description=sample.get("task_metadata", {}).get("task_description", ""),
                    task_type=task_type,
                )
                beam_candidates = beam_cands[:5] if beam_cands else []
                set_predictor_tokens = getattr(inferencer, "last_token_prior", None)
            except Exception as exc:
                beam_error = f"{type(exc).__name__}: {exc}"
                print(f"  [WARN] Beam inference failed for task_type={task_type!r}: {beam_error}")

        # ── Run selector ──
        sel_result = selector.select(
            retrieval_candidates=ret_candidates,
            beam_candidates=beam_candidates,
            task_type=task_type,
            expected_length=expected_len,
            set_predictor_tokens=set_predictor_tokens,
        )

        # ── Baselines ──
        # Retrieval top-1
        ret_top1_tokens = ret_candidates[0]["tokens"] if ret_candidates else []
        ret_eval = usability_evaluator.evaluate(ret_top1_tokens, task_type)
        ret_usable = ret_eval.usable
        ret_failures = list(ret_eval.failure_taxonomy)

        # Beam top-1
        beam_top1_tokens = []
        beam_usable = False
        beam_failures: list[str] = []
        if beam_candidates:
            bc = beam_candidates[0]
            beam_top1_tokens = _content_tokens(
                getattr(bc, "tokens", []) if hasattr(bc, "tokens") else []
            )
            beam_eval = usability_evaluator.evaluate(beam_top1_tokens, task_type)
            beam_usable = beam_eval.usable
            beam_failures = list(beam_eval.failure_taxonomy)

        # Selector selected
        sel_top1 = sel_result.selected
        sel_tokens = sel_top1.tokens if sel_top1 else []
        sel_eval = usability_evaluator.evaluate(sel_tokens, task_type)
        sel_usable = sel_eval.usable
        sel_failures = list(sel_eval.failure_taxonomy)

        # ── Oracle (any usable in the full candidate pool, not top-k truncation) ──
        full_pool = selector._build_candidate_pool(
            retrieval_candidates=ret_candidates,
            beam_candidates=beam_candidates,
        )
        pool_usable = 0
        oracle_best_score = 0.0
        oracle_best_tokens: list[int] = []
        pool_candidates: list[dict] = []
        for c in full_pool:
            # Compute features if not already done
            if c.features is None:
                c.features = selector._compute_features(
                    c, task_type=task_type, expected_length=expected_len,
                    set_predictor_tokens=set_predictor_tokens,
                )
            cand_eval = usability_evaluator.evaluate(c.tokens, task_type)
            pool_candidates.append({
                "tokens": c.tokens,
                "source": c.source,
                "logprob": c.logprob,
                "features": dict(c.features.score_components),
                "final_score": c.features.final_score if c.features else 0.0,
                "flags": list(c.features.flags) if c.features else [],
                "usable": cand_eval.usable,
                "usability_score": cand_eval.usability_score,
                "failure_taxonomy": list(cand_eval.failure_taxonomy),
            })
            if cand_eval.usable:
                pool_usable += 1
            if cand_eval.usability_score > oracle_best_score:
                oracle_best_score = cand_eval.usability_score
                oracle_best_tokens = list(c.tokens)

        # ── Final selection policy ──
        final_usable = False
        final_policy = selection_policy
        final_tokens: list[int] = []
        final_source = ""
        final_failures: list[str] = []
        if selection_policy == "beam_usable_quality" and beam_candidates:
            # Evaluate all beam candidates, pick best usable by quality
            best_quality = float("-inf")
            quality_tokens: list[int] = []
            for bc in beam_candidates:
                bc_tokens = _content_tokens(
                    getattr(bc, "tokens", []) if hasattr(bc, "tokens") else []
                )
                bc_eval = usability_evaluator.evaluate(bc_tokens, task_type)
                if not bc_eval.usable:
                    continue
                quality_score = _quality_adjusted_score(
                    bc_eval.usability_score,
                    bc_tokens,
                    bc_eval.failure_taxonomy,
                    token_names,
                )
                if quality_score > best_quality:
                    best_quality = quality_score
                    quality_tokens = list(bc_tokens)
            if quality_tokens:
                final_usable = True
                final_tokens = quality_tokens
                final_source = "beam"
                final_failures = []
            else:
                final_usable = sel_usable
                final_tokens = list(sel_tokens)
                final_source = sel_result.selected_source
                final_failures = [] if final_usable else list(sel_failures)
        elif selection_policy == "beam_first_usable" and beam_usable:
            final_usable = True
            final_tokens = list(beam_top1_tokens)
            final_source = "beam"
            final_failures = []
        elif selection_policy == "beam_first" and beam_candidates:
            final_usable = beam_usable
            final_tokens = list(beam_top1_tokens) if beam_top1_tokens else []
            final_source = "beam"
            final_failures = [] if final_usable else list(beam_failures)
        else:
            final_usable = sel_usable
            final_tokens = list(sel_tokens)
            final_source = sel_result.selected_source
            final_failures = [] if final_usable else list(sel_failures)

        # ── Record ──
        record = {
            "sample_index": sample_index,
            "selection_policy": final_policy,
            "final_usable": final_usable,
            "final_tokens": final_tokens,
            "final_source": final_source,
            "final_failures": final_failures,
            "split": split,
            "task_type": task_type,
            "task_metadata": {
                "task_type": task_meta.get("task_type", task_type),
                "task_type_normalized": task_meta.get("task_type_normalized", task_type),
                "task_name": task_meta.get("task_name", ""),
                "task_description": task_meta.get("task_description", ""),
            },
            "task_description": task_desc[:200],
            "ref_tokens": ref_tokens,
            "ref_len": len(ref_tokens),
            "expected_len": expected_len,
            "retrieval_top1_usable": ret_usable,
            "retrieval_top1_failures": ret_failures,
            "retrieval_top1_tokens": ret_top1_tokens,
            "beam_top1_usable": beam_usable,
            "beam_top1_failures": beam_failures,
            "beam_top1_tokens": beam_top1_tokens,
            "beam_error": beam_error,
            "set_predictor_prior_size": len(set_predictor_tokens or {}),
            "set_predictor_prior_over_0_3": sum(
                1 for p in (set_predictor_tokens or {}).values() if p > 0.3
            ),
            "selector_top1_usable": sel_usable,
            "selector_top1_failures": sel_failures,
            "selector_top1_tokens": sel_tokens,
            "selector_top1_source": sel_result.selected_source,
            "selector_pool_size": len(full_pool),
            "selector_ranked_topk_size": len(sel_result.ranked_candidates),
            "selector_pool_usable_count": pool_usable,
            "oracle_best_usability_score": round(oracle_best_score, 6),
            "oracle_best_tokens": oracle_best_tokens,
            "selector_trace": sel_result.selection_trace[:3],  # top-3 trace
            "source_counts": sel_result.source_counts,
            "pool_candidates": pool_candidates,  # ALL candidates with features+usable labels
        }

        # Final-specific diagnostics
        if final_tokens:
            final_eval = usability_evaluator.evaluate(final_tokens, task_type)
            record["final_failures"] = (
                list(final_eval.failure_taxonomy) if not final_eval.usable else []
            )
            record["final_warnings"] = (
                list(final_eval.failure_taxonomy) if final_eval.usable else []
            )
        else:
            record["final_failures"] = ["empty_final"]
            record["final_warnings"] = []

        if qgis_landing_retriever is not None and qgis_landing_evaluator is not None:
            record["qgis_landing"] = _build_qgis_landing_record(
                retriever=qgis_landing_retriever,
                evaluator=qgis_landing_evaluator,
                task_text=task_desc,
                final_tokens=final_tokens,
                id_to_code=id_to_code,
                k=qgis_landing_k,
            )

        if sel_usable and not ret_usable and not beam_usable:
            selector_win_count += 1
        if sel_usable:
            source_win_counts[sel_result.selected_source] += 1
        if final_source:
            final_source_counts[final_source] += 1
        if final_usable:
            final_usable_source_counts[final_source] += 1
        if ret_usable or beam_usable:
            baseline_best_count += 1

        results.append(record)

    selector_usable_rate = compute_usable_rate([
        {"usable": r["selector_top1_usable"]} for r in results
    ])
    retrieval_usable_rate = compute_usable_rate([
        {"usable": r["retrieval_top1_usable"]} for r in results
    ])
    beam_usable_rate = compute_usable_rate([
        {"usable": r["beam_top1_usable"]} for r in results
    ]) if use_beam else 0.0

    oracle_usable_rate = sum(
        1 for r in results if r["selector_pool_usable_count"] > 0
    ) / max(len(results), 1)

    final_usable_rate = compute_usable_rate([
        {"usable": r["final_usable"]} for r in results
    ])

    qgis_landing_records = [
        r.get("qgis_landing", {}) for r in results
        if r.get("qgis_landing", {}).get("enabled")
    ]
    qgis_landing_summary = {}
    if qgis_landing_records:
        n_land = len(qgis_landing_records)
        qgis_landing_summary = {
            "enabled": True,
            "num_records": n_land,
            "top1_valid_rate": sum(1 for r in qgis_landing_records if r.get("top1_valid")) / n_land,
            "avg_top1_quality": sum(float(r.get("top1_quality", 0.0)) for r in qgis_landing_records) / n_land,
            "l3_bridge_rate": sum(1 for r in qgis_landing_records if r.get("l3_bridge_hit")) / n_land,
            "native_bridge_rate": sum(1 for r in qgis_landing_records if r.get("native_bridge_hit")) / n_land,
            "combined_bridge_rate": sum(1 for r in qgis_landing_records if r.get("combined_bridge_hit")) / n_land,
        }
    else:
        qgis_landing_summary = {"enabled": False}

    return {
        "num_samples": len(results),
        "split": split,
        "use_beam": use_beam,
        "retrieval_k": retrieval_k,
        "selection_policy": selection_policy,
        "qgis_landing": qgis_landing_summary,
        "final_usable_rate": final_usable_rate,
        "selector_usable_rate": selector_usable_rate,
        "retrieval_top1_usable_rate": retrieval_usable_rate,
        "beam_top1_usable_rate": beam_usable_rate,
        "oracle_pool_usable_rate": oracle_usable_rate,
        "selector_wins_over_baselines": selector_win_count,
        "baseline_best_count": baseline_best_count,
        "source_win_counts": dict(source_win_counts),
        "final_source_counts": dict(final_source_counts),
        "final_usable_source_counts": dict(final_usable_source_counts),
        "selector_config": artifacts["selector_config"],
        "per_sample": results,
        "failure_taxonomy": _failure_taxonomy(results),
        "final_failure_taxonomy": _failure_taxonomy(results, "final_failures"),
        "final_warning_taxonomy": _failure_taxonomy(results, "final_warnings"),
    }


def _failure_taxonomy(results: list[dict], key: str = "selector_top1_failures") -> dict[str, int]:
    counts: Counter = Counter()
    for r in results:
        for f in r.get(key, []):
            counts[f] += 1
    return dict(counts.most_common())


# ═══════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════

def _ci(rate: float, n: int) -> str:
    if n == 0:
        return "N/A"
    se = math.sqrt(rate * (1 - rate) / n)
    lo = max(0.0, rate - 1.96 * se)
    hi = min(1.0, rate + 1.96 * se)
    return f"[{lo:.4f}, {hi:.4f}]"


def write_reports(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    with (output_dir / "selector_report.json").open("w", encoding="utf-8") as f:
        json.dump({
            "schema": SCHEMA_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **{k: v for k, v in report.items() if k != "per_sample"},
            "per_sample": report["per_sample"],
        }, f, ensure_ascii=False, indent=2)

    # CSV
    with (output_dir / "selected_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_type", "task_desc", "policy", "final_source", "final_usable",
            "beam_usable", "selector_usable", "retrieval_usable",
            "pool_usable_count", "final_tokens", "top_failures",
        ])
        for r in report["per_sample"]:
            writer.writerow([
                r["task_type"], r["task_description"][:100],
                r.get("selection_policy", ""), r["final_source"], r["final_usable"],
                r["beam_top1_usable"], r["selector_top1_usable"], r["retrieval_top1_usable"],
                r["selector_pool_usable_count"],
                "→".join(str(t) for t in r.get("final_tokens", [])[:10]),
                ";".join(r.get("final_failures", [])[:5]) if not r.get("final_usable") else "",
            ])

    # Markdown
    n = report["num_samples"]
    sel = report["selector_usable_rate"]
    ret = report["retrieval_top1_usable_rate"]
    beam = report["beam_top1_usable_rate"]
    final = report["final_usable_rate"]
    oracle = report["oracle_pool_usable_rate"]
    policy = report.get("selection_policy", "selector")

    md_lines = [
        "# Execution-Aware Selector Evaluation",
        "",
        f"**Samples**: {n}",
        f"**Selection policy**: {policy}",
        f"**Beam enabled**: {report['use_beam']}",
        f"**Retrieval K**: {report['retrieval_k']}",
        "",
        "## Usable Rate Comparison",
        "",
        "| Method | Top-1 Usable | 95% CI |",
        "|--------|:-----------:|--------|",
        f"| Retrieval top-1 | {ret*100:.1f}% | {_ci(ret, n)} |",
    ]
    if report["use_beam"]:
        md_lines.append(f"| Beam top-1 | {beam*100:.1f}% | {_ci(beam, n)} |")
    md_lines.extend([
        f"| Selector | {sel*100:.1f}% | {_ci(sel, n)} |",
        f"| **FINAL ({policy})** | **{final*100:.1f}%** | **{_ci(final, n)}** |",
        f"| *Oracle (pool)* | *{oracle*100:.1f}%* | *{_ci(oracle, n)}* |",
        "",
        "## Wins / Losses",
        "",
        f"- Selector outperforms both baselines: **{report['selector_wins_over_baselines']}** / {n}",
        f"- Either baseline usable: **{report['baseline_best_count']}** / {n}",
    ])

    if report.get("final_source_counts"):
        md_lines.append("")
        md_lines.append("### Final Selected Source Distribution")
        md_lines.append("")
        for src, cnt in sorted(report["final_source_counts"].items()):
            md_lines.append(f"- {src}: {cnt}")

    if report.get("final_usable_source_counts"):
        md_lines.append("")
        md_lines.append("### Final Usable Source Distribution")
        md_lines.append("")
        for src, cnt in sorted(report["final_usable_source_counts"].items()):
            md_lines.append(f"- {src}: {cnt}")

    if report.get("source_win_counts"):
        md_lines.append("")
        md_lines.append("### Selector Usable Source Distribution")
        md_lines.append("")
        for src, cnt in sorted(report["source_win_counts"].items()):
            md_lines.append(f"- {src}: {cnt}")

    if report.get("final_failure_taxonomy"):
        md_lines.append("")
        md_lines.append("### Final Failure Taxonomy")
        md_lines.append("")
        for failure, cnt in report["final_failure_taxonomy"].items():
            md_lines.append(f"- {failure}: {cnt}")

    if report.get("final_warning_taxonomy"):
        md_lines.append("")
        md_lines.append("### Final Warning Taxonomy")
        md_lines.append("")
        md_lines.append("Warnings are non-blocking issues on final usable samples.")
        md_lines.append("")
        for warning, cnt in report["final_warning_taxonomy"].items():
            md_lines.append(f"- {warning}: {cnt}")

    if report.get("failure_taxonomy"):
        md_lines.append("")
        md_lines.append("### Selector Failure Taxonomy")
        md_lines.append("")
        for failure, cnt in report["failure_taxonomy"].items():
            md_lines.append(f"- {failure}: {cnt}")

    md_lines.append("")
    md_lines.append("## Selector Configuration")
    md_lines.append("")
    md_lines.append("```json")
    md_lines.append(json.dumps(report["selector_config"], indent=2, ensure_ascii=False))
    md_lines.append("```")

    with (output_dir / "selector_report.md").open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n  Reports written to {output_dir}/")
    print(f"    selector_report.json")
    print(f"    selector_report.md")
    print(f"    selected_candidates.csv")


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(V4_QG_LABELED_WORKFLOWS_PATH))
    parser.add_argument("--splits", default=str(V4_QG_SPLITS_PATH))
    parser.add_argument("--hierarchy", default=str(CLASSIFICATION_HIERARCHY))
    parser.add_argument("--id-mappings", default=str(ID_MAPPINGS_PATH))
    parser.add_argument("--io-types", default=str(OUTPUT_DIR / "qgis_operator_io_types.json"))
    parser.add_argument("--transition-matrix", default=str(OUTPUT_DIR / "transition_allowed_next.json"))
    parser.add_argument("--length-stats", default=str(OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "task_type_length_stats.json"))
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--num-samples", type=int, default=200)
    parser.add_argument("--use-beam", action="store_true")
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--set-predictor-checkpoint", type=str, default=None)
    parser.add_argument("--retrieval-k", type=int, default=10)
    parser.add_argument("--selection-policy", type=str, default="selector",
                        choices=["selector", "beam_first_usable", "beam_first", "beam_usable_quality"],
                        help="Final selection policy (default: selector)")
    parser.add_argument("--use-qgis-landing", action="store_true",
                        help="Run QGIS chain landing as shadow diagnostics after final L3 selection")
    parser.add_argument("--qgis-chain-dataset", default=str(OUTPUT_DIR / "qgis_chain_dataset.jsonl"))
    parser.add_argument("--qgis-catalog", default=str(ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"))
    parser.add_argument("--qgis-landing-k", type=int, default=5)
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR_PATH))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    import random
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    print("=" * 70)
    print("Execution-Aware Selector Evaluation")
    print("=" * 70)
    print(f"  Samples: {args.num_samples}")
    print(f"  Split: {args.split}")
    print(f"  Beam: {args.use_beam}")
    print(f"  Selection policy: {args.selection_policy}")
    print(f"  QGIS landing: {args.use_qgis_landing}")
    print(f"  Retrieval K: {args.retrieval_k}")
    if args.selection_policy.startswith("beam_first") and not args.use_beam:
        print("  [WARN] beam_first* policy selected but --use-beam is off; final will fallback to selector")

    # Resolve checkpoint
    ckpt_path = None
    if args.use_beam:
        if args.checkpoint:
            ckpt_path = Path(args.checkpoint)
        else:
            gen_f1 = V4_6_QG_TRANSFORMER_CHECKPOINT_DIR / "best_gen_set_f1_model.pth"
            best_path = V4_6_QG_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
            ckpt_path = gen_f1 if gen_f1.exists() else best_path
        print(f"  Checkpoint: {ckpt_path}")

    sp_ckpt_path = None
    if args.use_beam:
        if args.set_predictor_checkpoint:
            sp_ckpt_path = Path(args.set_predictor_checkpoint)
        else:
            default_sp = V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
            sp_ckpt_path = default_sp if default_sp.exists() else None
        print(f"  Set Predictor checkpoint: {sp_ckpt_path if sp_ckpt_path else 'disabled'}")

    print("\n[1] Loading metadata and building selector...")
    artifacts = build_selector_artifacts(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        hierarchy_path=Path(args.hierarchy),
        id_mappings_path=Path(args.id_mappings),
        io_types_path=Path(args.io_types),
        transition_path=Path(args.transition_matrix),
        length_stats_path=Path(args.length_stats) if Path(args.length_stats).exists() else Path("."),
    )
    print(f"  Selector: {artifacts['selector_config']['num_qgis_mapped_tokens']} mappable tokens, "
          f"{artifacts['selector_config']['num_transition_states']} transition states")
    print(f"  Train: {len(artifacts['train_wf'])}, Val: {len(artifacts['val_wf'])}, Test: {len(artifacts['test_wf'])}")

    print(f"\n[2] Running evaluation on {args.num_samples} samples...")
    report = evaluate(
        artifacts=artifacts,
        num_samples=args.num_samples,
        split=args.split,
        use_beam=args.use_beam,
        checkpoint_path=ckpt_path,
        set_predictor_checkpoint_path=sp_ckpt_path,
        retrieval_k=args.retrieval_k,
        selection_policy=args.selection_policy,
        use_qgis_landing=args.use_qgis_landing,
        qgis_landing_dataset_path=Path(args.qgis_chain_dataset),
        qgis_landing_catalog_path=Path(args.qgis_catalog),
        qgis_landing_k=args.qgis_landing_k,
    )

    print(f"\n[3] Results ({report.get('selection_policy', 'selector')}):")
    print(f"  Retrieval top-1 usable:  {report['retrieval_top1_usable_rate']*100:.1f}%  {_ci(report['retrieval_top1_usable_rate'], report['num_samples'])}")
    if args.use_beam:
        print(f"  Beam top-1 usable:      {report['beam_top1_usable_rate']*100:.1f}%  {_ci(report['beam_top1_usable_rate'], report['num_samples'])}")
    print(f"  Selector top-1 usable:  {report['selector_usable_rate']*100:.1f}%  {_ci(report['selector_usable_rate'], report['num_samples'])}")
    print(f"  FINAL ({report.get('selection_policy', 'selector')}): {report['final_usable_rate']*100:.1f}%  {_ci(report['final_usable_rate'], report['num_samples'])}")
    print(f"  Oracle pool usable:     {report['oracle_pool_usable_rate']*100:.1f}%  {_ci(report['oracle_pool_usable_rate'], report['num_samples'])}")
    print(f"  Selector wins: {report['selector_wins_over_baselines']}/{report['num_samples']}")
    if report.get("qgis_landing", {}).get("enabled"):
        landing = report["qgis_landing"]
        print(f"  QGIS landing valid:     {landing['top1_valid_rate']*100:.1f}%")
        print(f"  QGIS combined bridge:   {landing['combined_bridge_rate']*100:.1f}%")
        print(f"  QGIS avg quality:       {landing['avg_top1_quality']:.4f}")

    if report.get("final_source_counts"):
        print(f"\n  Final selected source distribution:")
        for src, cnt in sorted(report["final_source_counts"].items()):
            print(f"    {src}: {cnt}")

    print(f"\n[4] Writing reports...")
    write_reports(report, Path(args.output_dir))
    return report


if __name__ == "__main__":
    main()
