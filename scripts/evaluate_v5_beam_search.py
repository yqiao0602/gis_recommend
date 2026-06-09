#!/usr/bin/env python3
"""Evaluate an existing V5_final checkpoint across beam widths.

This is evaluation tooling only: it loads the checkpoint strictly through the
V5 loader, decodes from direct runtime inputs, and writes report artifacts.  It
does not train, mutate checkpoints, or feed diagnostics back into execution.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.models.v5_final import (  # noqa: E402
    IOMaskBuilder,
    build_v5_empirical_prediction_record,
    load_v5_final_model,
)
from gis_recommend.training.train_v5 import V5WorkflowDataset  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.beam_search_eval.v1"


def select_candidate(candidates: Sequence[dict], *, length_norm_alpha: float = 0.0) -> dict:
    """Select one candidate using explicit raw or length-normalized score."""

    if not candidates:
        return {"rank": 0, "tokens": [], "score": float("-inf"), "selection_score": float("-inf")}
    alpha = max(float(length_norm_alpha), 0.0)

    def selection_score(row: dict) -> float:
        score = float(row.get("score", float("-inf")))
        if alpha <= 0.0:
            return score
        length = max(len(row.get("tokens") or []), 1)
        return score / (float(length) ** alpha)

    selected = max(candidates, key=lambda row: (selection_score(row), -int(row.get("rank", 0))))
    out = dict(selected)
    out["selection_score"] = round(selection_score(selected), 8)
    out["selection_policy"] = "length_normalized" if alpha > 0.0 else "raw_logprob"
    return out


def beam_oracle_metrics(candidates: Sequence[dict], reference: Sequence[int]) -> dict:
    ref = [int(token) for token in reference]
    rows = []
    for row in candidates:
        pred = [int(token) for token in row.get("tokens", [])]
        metrics = _basic_metrics(pred, ref)
        rows.append({"tokens": pred, **metrics})
    best_lcs = max(rows, key=lambda row: (row["lcs_ratio"], row["token_accuracy"], row["sequence_em"]), default=None)
    best_token = max(rows, key=lambda row: (row["token_accuracy"], row["lcs_ratio"], row["sequence_em"]), default=None)
    return {
        "beam_count": len(rows),
        "best_oracle_lcs_ratio": float(best_lcs["lcs_ratio"]) if best_lcs else 0.0,
        "best_oracle_token_accuracy": float(best_token["token_accuracy"]) if best_token else 0.0,
        "reference_in_beam": any(row.get("sequence_em") == 1.0 for row in rows),
        "best_lcs_tokens": list(best_lcs["tokens"]) if best_lcs else [],
        "best_token_accuracy_tokens": list(best_token["tokens"]) if best_token else [],
    }


def beam_diversity_metrics(candidates: Sequence[dict]) -> dict:
    seqs = [tuple(int(token) for token in row.get("tokens", [])) for row in candidates]
    unique = set(seqs)
    distances = []
    for i, left in enumerate(seqs):
        for right in seqs[i + 1 :]:
            distances.append(1.0 - _lcs_ratio(left, right))
    lengths = [len(seq) for seq in seqs]
    return {
        "candidate_count": len(seqs),
        "unique_sequences": len(unique),
        "unique_sequence_ratio": round(len(unique) / len(seqs), 8) if seqs else 0.0,
        "avg_pairwise_lcs_distance": round(sum(distances) / len(distances), 8) if distances else 0.0,
        "min_candidate_length": min(lengths) if lengths else 0,
        "max_candidate_length": max(lengths) if lengths else 0,
        "avg_candidate_length": round(sum(lengths) / len(lengths), 8) if lengths else 0.0,
    }


def evaluate_checkpoint_beams(
    *,
    checkpoint: Path,
    data_path: Path,
    splits_path: Path,
    transition_matrix: Optional[Path],
    output_dir: Path,
    beam_widths: Sequence[int],
    eval_samples: int,
    device: str,
    length_norm_alpha: float,
) -> dict:
    model, checkpoint_payload = load_v5_final_model(checkpoint, map_location=device)
    torch_device = torch.device(device)
    model = model.to(torch_device)
    model_config = model.config
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    test_indices = _validated_indices(splits.get("test_indices", []), len(workflows))
    test_dataset = V5WorkflowDataset([workflows[i] for i in test_indices], model_config)
    io_mask_builder = _build_io_mask_builder(transition_matrix, model_config)
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    for width in [int(value) for value in beam_widths]:
        report, traces = _evaluate_one_width(
            model=model,
            model_config=model_config,
            test_dataset=test_dataset,
            test_indices=test_indices,
            checkpoint=checkpoint,
            checkpoint_payload=checkpoint_payload,
            io_mask_builder=io_mask_builder,
            beam_width=width,
            eval_samples=eval_samples,
            length_norm_alpha=length_norm_alpha,
            device=torch_device,
        )
        report_path = output_dir / f"beam_{width}_report.json"
        trace_path = output_dir / f"decode_traces_beam_{width}.json"
        _write_json(report_path, report)
        _write_json(trace_path, traces)
        reports.append(
            {
                "beam_width": width,
                "report_path": str(report_path),
                "decode_trace_path": str(trace_path),
                "metrics": report["metrics"],
                "beam_oracle": report["beam_oracle"],
                "diversity": report["diversity"],
            }
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": str(checkpoint),
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "transition_matrix": str(transition_matrix) if transition_matrix else None,
        "eval_samples": int(eval_samples),
        "length_normalization": {
            "enabled": float(length_norm_alpha) > 0.0,
            "alpha": float(length_norm_alpha),
            "selection_policy": "length_normalized" if float(length_norm_alpha) > 0.0 else "raw_logprob",
        },
        "reports": reports,
        "runtime_contract": {
            "retrained_model": False,
            "checkpoint_mutated": False,
            "diagnostics_gate_execution": False,
        },
    }
    summary_path = output_dir / "beam_search_summary.json"
    markdown_path = output_dir / "beam_search_summary.md"
    _write_json(summary_path, summary)
    _write_markdown(markdown_path, summary)
    return summary


def _evaluate_one_width(
    *,
    model,
    model_config,
    test_dataset: V5WorkflowDataset,
    test_indices: Sequence[int],
    checkpoint: Path,
    checkpoint_payload: dict,
    io_mask_builder: Optional[IOMaskBuilder],
    beam_width: int,
    eval_samples: int,
    length_norm_alpha: float,
    device: torch.device,
) -> tuple[dict, dict]:
    samples = []
    traces = []
    metrics_rows = []
    oracle_rows = []
    diversity_rows = []
    limit = min(int(eval_samples), len(test_dataset))
    for local_index in range(limit):
        row = test_dataset[local_index]
        task_embeddings = row["task_embeddings"].unsqueeze(0).to(device)
        reference = _reference_tokens(row, model_config)
        if int(beam_width) <= 1:
            decoded = [
                model.decode_greedy(
                    task_embeddings=task_embeddings,
                    io_mask_builder=io_mask_builder,
                    max_len=model_config.max_seq_len,
                )
            ]
        else:
            decoded = model.decode_beam(
                task_embeddings=task_embeddings,
                io_mask_builder=io_mask_builder,
                max_len=model_config.max_seq_len,
                beam_width=int(beam_width),
            )
        candidates = [_candidate_from_result(result, rank, length_norm_alpha) for rank, result in enumerate(decoded)]
        selected = select_candidate(candidates, length_norm_alpha=length_norm_alpha)
        selected_result = decoded[int(selected.get("rank", 0))]
        selected_result.beam_candidates = [_json_candidate(row) for row in candidates]
        record = build_v5_empirical_prediction_record(
            sample_id=str(local_index),
            decode_result=selected_result,
            reference_tokens=reference,
            retrieval_diagnostics={"retrieval_used": False, "attribution": "none"},
            checkpoint_metadata={
                "checkpoint_path": str(checkpoint),
                "model_version": checkpoint_payload.get("provenance", {}).get("model_version", "v5_final"),
            },
        )
        record["metrics"]["io_validity"] = _io_validity(selected_result.operator_ids, io_mask_builder)
        record["selection"] = {
            "selected_rank": int(selected.get("rank", 0)),
            "selection_score": selected.get("selection_score"),
            "selection_policy": selected.get("selection_policy"),
            "length_norm_alpha": float(length_norm_alpha),
        }
        oracle = beam_oracle_metrics(candidates, reference)
        diversity = beam_diversity_metrics(candidates)
        record["beam_oracle_metrics"] = oracle
        record["decode_diversity"] = diversity
        metrics_rows.append(record["metrics"])
        oracle_rows.append(oracle)
        diversity_rows.append(diversity)
        samples.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_indices[local_index]),
                "reference_tokens": reference,
                "predictions": {"v5_final": record},
            }
        )
        traces.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_indices[local_index]),
                "reference_tokens": reference,
                "selected_rank": int(selected.get("rank", 0)),
                "candidates": [
                    {
                        **_json_candidate(candidate),
                        "decode_trace": list(candidate.get("decode_trace", [])),
                        "alpha_trace": list(candidate.get("alpha_trace", [])),
                    }
                    for candidate in candidates
                ],
            }
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "beam_width": int(beam_width),
        "checkpoint_metadata": {
            "checkpoint_path": str(checkpoint),
            "checkpoint_format": checkpoint_payload.get("provenance", {}).get("format_version"),
            "model_version": checkpoint_payload.get("provenance", {}).get("model_version"),
            "architecture": checkpoint_payload.get("provenance", {}).get("architecture"),
        },
        "length_normalization": {
            "enabled": float(length_norm_alpha) > 0.0,
            "alpha": float(length_norm_alpha),
        },
        "metrics": _aggregate_metrics(metrics_rows),
        "beam_oracle": _aggregate_oracle(oracle_rows),
        "diversity": _aggregate_diversity(diversity_rows),
        "samples": samples,
        "runtime_contract": {
            "retrained_model": False,
            "checkpoint_mutated": False,
            "diagnostics_gate_execution": False,
        },
    }
    return report, {
        "schema_version": "gis_recommend.v5_final.decode_traces.v1",
        "beam_width": int(beam_width),
        "checkpoint": str(checkpoint),
        "samples": traces,
    }


def _candidate_from_result(result, rank: int, length_norm_alpha: float) -> dict:
    base = result.beam_candidates[0] if result.beam_candidates else {}
    score = float(base.get("score", 0.0))
    tokens = [int(token) for token in result.operator_ids]
    candidate = {
        "rank": int(rank),
        "tokens": tokens,
        "score": round(score, 8),
        "operator_names": list(result.operator_names),
        "termination_reason": result.termination_reason,
        "end_timing": dict(result.end_timing),
        "repetition_statistics": dict(result.repetition_statistics),
        "decode_trace": list(result.decode_trace),
        "alpha_trace": list(result.alpha_trace),
        "token_probabilities": list(result.token_probabilities),
    }
    if float(length_norm_alpha) > 0.0:
        length = max(len(tokens), 1)
        candidate["length_normalized_score"] = round(score / (length ** float(length_norm_alpha)), 8)
    return candidate


def _json_candidate(candidate: dict) -> dict:
    keep = [
        "rank",
        "tokens",
        "score",
        "length_normalized_score",
        "operator_names",
        "termination_reason",
        "end_timing",
        "repetition_statistics",
    ]
    return {key: copy.deepcopy(candidate[key]) for key in keep if key in candidate}


def _reference_tokens(row: dict, model_config) -> list[int]:
    specials = {
        model_config.resolved_pad_token_id,
        model_config.start_token_id,
        model_config.resolved_end_token_id,
    }
    return [
        int(token)
        for token, is_pad in zip(row["operator_input_ids"].tolist(), row["pad_mask"].tolist())
        if not is_pad and int(token) not in specials
    ]


def _basic_metrics(pred: Sequence[int], ref: Sequence[int]) -> dict:
    pred = [int(token) for token in pred]
    ref = [int(token) for token in ref]
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    lcs = _lcs_length(pred, ref)
    positional = sum(1 for left, right in zip(pred, ref) if left == right) / max(len(ref), 1) if ref else 0.0
    return {
        "set_f1": round(set_f1, 6),
        "lcs_ratio": round(lcs / max(len(pred), len(ref), 1), 6),
        "token_accuracy": round(positional, 6),
        "sequence_em": float(pred == ref),
        "length_ratio": round(len(pred) / len(ref), 6) if ref else 0.0,
        "length_accuracy": float(len(pred) == len(ref)),
        "abs_length_error": abs(len(pred) - len(ref)),
    }


def _aggregate_metrics(rows: Sequence[dict]) -> dict:
    keys = [
        "set_f1",
        "lcs_ratio",
        "sequence_em",
        "length_ratio",
        "token_accuracy",
        "length_accuracy",
        "abs_length_error",
        "io_validity",
    ]
    out = {"n": len(rows)}
    for key in keys:
        out[key] = round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8)
    out["exact_match"] = out["sequence_em"]
    out["avg_abs_length_error"] = out.pop("abs_length_error")
    return out


def _aggregate_oracle(rows: Sequence[dict]) -> dict:
    if not rows:
        return {
            "mean_best_oracle_lcs_ratio": 0.0,
            "mean_best_oracle_token_accuracy": 0.0,
            "reference_in_beam_rate": 0.0,
        }
    return {
        "mean_best_oracle_lcs_ratio": round(sum(float(row["best_oracle_lcs_ratio"]) for row in rows) / len(rows), 8),
        "mean_best_oracle_token_accuracy": round(sum(float(row["best_oracle_token_accuracy"]) for row in rows) / len(rows), 8),
        "reference_in_beam_rate": round(sum(1 for row in rows if row.get("reference_in_beam")) / len(rows), 8),
    }


def _aggregate_diversity(rows: Sequence[dict]) -> dict:
    keys = [
        "candidate_count",
        "unique_sequences",
        "unique_sequence_ratio",
        "avg_pairwise_lcs_distance",
        "avg_candidate_length",
    ]
    return {key: round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8) for key in keys}


def _io_validity(tokens: Sequence[int], io_mask_builder: Optional[IOMaskBuilder]) -> float:
    if io_mask_builder is None or len(tokens) <= 1:
        return 1.0
    for previous, current in zip(tokens, tokens[1:]):
        if not io_mask_builder.are_compatible(int(previous), int(current)):
            return 0.0
    return 1.0


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            cur[idx] = prev[idx - 1] + 1 if int(token) == int(other) else max(prev[idx], cur[idx - 1])
        prev = cur
    return prev[-1]


def _lcs_ratio(a: Sequence[int], b: Sequence[int]) -> float:
    return _lcs_length(a, b) / max(len(a), len(b), 1)


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", payload)
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid workflows payload: {path}")
    return workflows


def _validated_indices(indices: Sequence[int], total: int) -> list[int]:
    out = [int(index) for index in indices]
    for index in out:
        if index < 0 or index >= total:
            raise IndexError(f"Split index {index} out of range for {total} workflows")
    return out


def _build_io_mask_builder(path: Optional[Path], model_config) -> Optional[IOMaskBuilder]:
    if path is None or not Path(path).exists():
        return None
    return IOMaskBuilder.from_transition_matrix(
        path,
        vocab_size=model_config.vocab_size,
        end_token_id=model_config.resolved_end_token_id,
        blocked_token_ids={model_config.resolved_pad_token_id, model_config.start_token_id},
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, summary: dict) -> None:
    lines = [
        "# V5_final Beam Search Evaluation",
        "",
        f"Checkpoint: `{summary.get('checkpoint')}`",
        f"Eval samples: `{summary.get('eval_samples')}`",
        f"Length normalization: `{summary.get('length_normalization', {}).get('selection_policy')}`",
        "",
        "## Beam Metrics",
        "",
        "| Beam | Exact | Token Acc | LCS | SetF1 | Oracle LCS | Oracle Token Acc | Unique Ratio | Diversity |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.get("reports", []):
        metrics = row.get("metrics", {})
        oracle = row.get("beam_oracle", {})
        diversity = row.get("diversity", {})
        lines.append(
            "| {beam} | {exact} | {tok} | {lcs} | {setf1} | {olcs} | {otok} | {uniq} | {div} |".format(
                beam=row.get("beam_width"),
                exact=metrics.get("exact_match"),
                tok=metrics.get("token_accuracy"),
                lcs=metrics.get("lcs_ratio"),
                setf1=metrics.get("set_f1"),
                olcs=oracle.get("mean_best_oracle_lcs_ratio"),
                otok=oracle.get("mean_best_oracle_token_accuracy"),
                uniq=diversity.get("unique_sequence_ratio"),
                div=diversity.get("avg_pairwise_lcs_distance"),
            )
        )
    lines.extend(["", "Diagnostics and oracle metrics are report-only."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "stage1" / "checkpoints" / "best_model.pt")
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "beam_search_eval")
    parser.add_argument("--beam-widths", type=int, nargs="+", default=[1, 3, 5, 10])
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--length-norm-alpha", type=float, default=0.0)
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    summary = evaluate_checkpoint_beams(
        checkpoint=args.checkpoint,
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix=args.transition_matrix,
        output_dir=args.output_dir,
        beam_widths=args.beam_widths,
        eval_samples=args.eval_samples,
        device=args.device,
        length_norm_alpha=args.length_norm_alpha,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    main()
