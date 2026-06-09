#!/usr/bin/env python3
"""Minimal retrieval-assisted V5_final evaluation prototype.

The prototype uses lexical top-3 workflow retrieval as an eval-time conditioning
input by appending retrieved operator ids to the deterministic task embedding
text.  It adds no trainable modules and does not modify checkpoint semantics.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.evaluation import empirical as empirical_eval  # noqa: E402
from gis_recommend.models.v5_final import (  # noqa: E402
    IOMaskBuilder,
    build_v5_empirical_prediction_record,
    deterministic_task_embeddings,
    load_v5_final_model,
)

from scripts.evaluate_v5_beam_search import (  # noqa: E402
    beam_diversity_metrics,
    beam_oracle_metrics,
    select_candidate,
)


SCHEMA_VERSION = "gis_recommend.v5_final.retrieval_assisted_eval.v1"


def build_retrieval_conditioning_text(
    *,
    task_text: str,
    retrieved_sequences: Sequence[Sequence[int]],
    top_k: int = 3,
) -> str:
    parts = [str(task_text).strip() or "unknown task", "retrieval_context:"]
    for rank, seq in enumerate(list(retrieved_sequences)[: max(int(top_k), 0)], start=1):
        tokens = " ".join(str(int(token)) for token in seq)
        parts.append(f"retrieved_workflow_{rank}: {tokens}")
    return " | ".join(parts)


def retrieval_copy_attribution(
    *,
    generated_tokens: Sequence[int],
    retrieved_sequences: Sequence[Sequence[int]],
) -> dict:
    retrieved = set()
    for seq in retrieved_sequences:
        retrieved.update(int(token) for token in seq)
    copied = [int(token) for token in generated_tokens if int(token) in retrieved]
    novel = [int(token) for token in generated_tokens if int(token) not in retrieved]
    return {
        "copied_operators": copied,
        "novel_operators": novel,
        "copied_operator_count": len(copied),
        "novel_operator_count": len(novel),
        "copied_operator_ratio": round(len(copied) / len(generated_tokens), 8) if generated_tokens else 0.0,
        "novel_operator_ratio": round(len(novel) / len(generated_tokens), 8) if generated_tokens else 0.0,
    }


def evaluate_retrieval_assisted(
    *,
    checkpoint: Path,
    data_path: Path,
    splits_path: Path,
    transition_matrix: Optional[Path],
    output_dir: Path,
    eval_samples: int,
    beam_width: int,
    retrieval_top_k: int,
    device: str,
) -> dict:
    model, checkpoint_payload = load_v5_final_model(checkpoint, map_location=device)
    torch_device = torch.device(device)
    model = model.to(torch_device)
    model_config = model.config
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    train_indices = _validated_indices(splits.get("train_indices", []), len(workflows))
    test_indices = _validated_indices(splits.get("test_indices", []), len(workflows))
    train_items = empirical_eval._build_train_items(workflows, train_indices)
    retrieval_index = empirical_eval._build_retrieval_index(train_items, embedding_dim=128)
    io_mask_builder = _build_io_mask_builder(transition_matrix, model_config)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    aggregate: dict[str, list[dict]] = {
        "generation_only": [],
        "retrieval_only": [],
        "retrieval_assisted": [],
    }
    oracle_rows: dict[str, list[dict]] = {"generation_only": [], "retrieval_only": [], "retrieval_assisted": []}
    diversity_rows: dict[str, list[dict]] = {"generation_only": [], "retrieval_only": [], "retrieval_assisted": []}
    attribution_rows = []
    limit = min(int(eval_samples), len(test_indices))
    for local_index, test_index in enumerate(test_indices[:limit]):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        task_text = _task_text(workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        retrieved = empirical_eval._rank_retrieval(
            sample,
            train_items,
            mode="lexical",
            top_k=int(retrieval_top_k),
            embedding_dim=128,
            retrieval_index=retrieval_index,
        )
        retrieved_sequences = [list(row.get("tokens") or []) for row in retrieved[: int(retrieval_top_k)]]
        generation_record, generation_candidates = _decode_record(
            method="generation_only",
            model=model,
            model_config=model_config,
            task_text=task_text,
            reference=reference,
            checkpoint=checkpoint,
            checkpoint_payload=checkpoint_payload,
            io_mask_builder=io_mask_builder,
            beam_width=beam_width,
            device=torch_device,
            retrieved_sequences=[],
        )
        retrieval_record = _retrieval_only_record(
            retrieved=retrieved,
            reference=reference,
            io_mask_builder=io_mask_builder,
        )
        conditioned_text = build_retrieval_conditioning_text(
            task_text=task_text,
            retrieved_sequences=retrieved_sequences,
            top_k=int(retrieval_top_k),
        )
        assisted_record, assisted_candidates = _decode_record(
            method="retrieval_assisted",
            model=model,
            model_config=model_config,
            task_text=conditioned_text,
            reference=reference,
            checkpoint=checkpoint,
            checkpoint_payload=checkpoint_payload,
            io_mask_builder=io_mask_builder,
            beam_width=beam_width,
            device=torch_device,
            retrieved_sequences=retrieved_sequences,
        )
        retrieval_record["retrieval_content"] = {
            "retrieved_sequences": copy.deepcopy(retrieved_sequences),
            "top_train_indices": [row.get("train_index") for row in retrieved],
        }
        generation_record["retrieval_content"] = {"retrieved_sequences": [], "top_train_indices": []}
        assisted_record["retrieval_content"] = {
            "retrieved_sequences": copy.deepcopy(retrieved_sequences),
            "top_train_indices": [row.get("train_index") for row in retrieved],
            "conditioning_text": conditioned_text,
        }

        for method, record, candidates in [
            ("generation_only", generation_record, generation_candidates),
            ("retrieval_only", retrieval_record, _candidate_pool_from_retrieval(retrieved)),
            ("retrieval_assisted", assisted_record, assisted_candidates),
        ]:
            aggregate[method].append(record["metrics"])
            oracle_rows[method].append(beam_oracle_metrics(candidates, reference))
            diversity_rows[method].append(beam_diversity_metrics(candidates))

        attribution_rows.append(assisted_record["retrieval_generation_attribution"])
        samples.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_index),
                "task_type": sample["task_type"],
                "reference_tokens": reference,
                "retrieved_content": copy.deepcopy(retrieved_sequences),
                "predictions": {
                    "generation_only": generation_record,
                    "retrieval_only": retrieval_record,
                    "retrieval_assisted": assisted_record,
                },
            }
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint_metadata": {
            "checkpoint_path": str(checkpoint),
            "checkpoint_format": checkpoint_payload.get("provenance", {}).get("format_version"),
            "model_version": checkpoint_payload.get("provenance", {}).get("model_version"),
            "architecture": checkpoint_payload.get("provenance", {}).get("architecture"),
        },
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "transition_matrix": str(transition_matrix) if transition_matrix else None,
        "eval_samples": limit,
        "beam_width": int(beam_width),
        "retrieval_top_k": int(retrieval_top_k),
        "conditioning": {
            "method": "deterministic_task_embedding_text_augmentation",
            "trainable_modules_added": False,
            "retrieved_sequences_used": int(retrieval_top_k),
        },
        "reference_policy": {
            "tokens": "full_workflow_content_tokens",
            "note": "All three methods in this report use the same full reference tokens; this report is not a direct replacement for the Stage1 truncated-horizon evaluation report.",
        },
        "metrics": {
            method: _aggregate_metrics(rows)
            for method, rows in aggregate.items()
        },
        "oracle_metrics": {
            method: _aggregate_oracle(rows)
            for method, rows in oracle_rows.items()
        },
        "diversity": {
            method: _aggregate_diversity(rows)
            for method, rows in diversity_rows.items()
        },
        "retrieval_generation_attribution": _aggregate_attribution(attribution_rows),
        "samples": samples,
        "runtime_contract": {
            "retrained_model": False,
            "new_trainable_modules": False,
            "checkpoint_mutated": False,
            "diagnostics_gate_execution": False,
        },
    }
    _write_json(output_dir / "retrieval_assisted_report.json", report)
    _write_markdown(output_dir / "retrieval_assisted_summary.md", report)
    _write_json(
        output_dir / "decode_traces.json",
        {
            "schema_version": "gis_recommend.v5_final.retrieval_assisted_traces.v1",
            "checkpoint": str(checkpoint),
            "samples": [
                {
                    "local_index": row["local_index"],
                    "source_test_index": row["source_test_index"],
                    "reference_tokens": row["reference_tokens"],
                    "retrieved_content": row["retrieved_content"],
                    "generation_only_trace": row["predictions"]["generation_only"].get("decode_trace", []),
                    "retrieval_assisted_trace": row["predictions"]["retrieval_assisted"].get("decode_trace", []),
                }
                for row in samples
            ],
        },
    )
    return report


def _decode_record(
    *,
    method: str,
    model,
    model_config,
    task_text: str,
    reference: Sequence[int],
    checkpoint: Path,
    checkpoint_payload: dict,
    io_mask_builder: Optional[IOMaskBuilder],
    beam_width: int,
    device: torch.device,
    retrieved_sequences: Sequence[Sequence[int]],
) -> tuple[dict, list[dict]]:
    task_embeddings = deterministic_task_embeddings(
        task_text,
        hidden_size=model_config.bert_hidden_size,
        device=device,
    )
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
    candidates = [_candidate_from_decode(result, rank) for rank, result in enumerate(decoded)]
    selected = select_candidate(candidates, length_norm_alpha=0.0)
    selected_result = decoded[int(selected.get("rank", 0))]
    selected_result.beam_candidates = [_candidate_artifact(row) for row in candidates]
    record = build_v5_empirical_prediction_record(
        sample_id=method,
        decode_result=selected_result,
        reference_tokens=reference,
        retrieval_diagnostics={"retrieval_used": bool(retrieved_sequences), "attribution": "conditioning_context" if retrieved_sequences else "none"},
        checkpoint_metadata={
            "checkpoint_path": str(checkpoint),
            "model_version": checkpoint_payload.get("provenance", {}).get("model_version", "v5_final"),
        },
    )
    record["method"] = method
    record["metrics"]["io_validity"] = _io_validity(selected_result.operator_ids, io_mask_builder)
    record["metrics"]["top5_sequence_accuracy"] = _topk_sequence_accuracy(candidates, reference, k=5)
    record["beam_oracle_metrics"] = beam_oracle_metrics(candidates, reference)
    record["decode_diversity"] = beam_diversity_metrics(candidates)
    record["retrieval_generation_attribution"] = {
        "retrieval_used": bool(retrieved_sequences),
        "conditioning_context_used": bool(retrieved_sequences),
        **retrieval_copy_attribution(
            generated_tokens=selected_result.operator_ids,
            retrieved_sequences=retrieved_sequences,
        ),
    }
    return record, candidates


def _retrieval_only_record(
    *,
    retrieved: Sequence[dict],
    reference: Sequence[int],
    io_mask_builder: Optional[IOMaskBuilder],
) -> dict:
    candidates = _candidate_pool_from_retrieval(retrieved)
    top = candidates[0] if candidates else {"tokens": []}
    pred = [int(token) for token in top.get("tokens", [])]
    metrics = _basic_metrics(pred, reference)
    metrics["io_validity"] = _io_validity(pred, io_mask_builder)
    metrics["top5_sequence_accuracy"] = _topk_sequence_accuracy(candidates, reference, k=5)
    return {
        "method": "retrieval_only",
        "pred_tokens": pred,
        "reference_tokens": [int(token) for token in reference],
        "beam_candidates": [_candidate_artifact(row) for row in candidates],
        "decode_trace": [
            {"step": idx + 1, "selected_token": int(token), "source": "lexical_retrieval"}
            for idx, token in enumerate(pred)
        ],
        "alpha_trace": [],
        "token_probabilities": [],
        "end_timing": {
            "predicted_content_length": len(pred),
            "reference_content_length": len(reference),
        },
        "repetition_statistics": _repetition_statistics(pred),
        "candidate_pool_diagnostics": {
            "pool_size": len(candidates),
            "unique_sequences": len({tuple(row.get("tokens", [])) for row in candidates}),
        },
        "retrieval_diagnostics": {
            "retrieval_used": True,
            "mode": "lexical",
            "top_score": retrieved[0].get("score") if retrieved else 0.0,
            "top_train_index": retrieved[0].get("train_index") if retrieved else None,
        },
        "metrics": metrics,
        "error_taxonomy": _basic_error_taxonomy(pred, reference),
        "beam_oracle_metrics": beam_oracle_metrics(candidates, reference),
        "decode_diversity": beam_diversity_metrics(candidates),
        "retrieval_generation_attribution": {
            "retrieval_used": True,
            "conditioning_context_used": False,
            "copied_operators": pred,
            "novel_operators": [],
            "copied_operator_count": len(pred),
            "novel_operator_count": 0,
            "copied_operator_ratio": 1.0 if pred else 0.0,
            "novel_operator_ratio": 0.0,
        },
        "runtime_gated_by_diagnostics": False,
    }


def _candidate_pool_from_retrieval(retrieved: Sequence[dict]) -> list[dict]:
    rows = []
    for rank, row in enumerate(retrieved):
        rows.append(
            {
                "rank": rank,
                "tokens": [int(token) for token in row.get("tokens", [])],
                "score": float(row.get("score", 0.0)),
                "train_index": row.get("train_index"),
                "lexical_score": row.get("lexical_score"),
                "task_type": row.get("task_type"),
            }
        )
    return rows


def _candidate_from_decode(result, rank: int) -> dict:
    base = result.beam_candidates[0] if result.beam_candidates else {}
    return {
        "rank": int(rank),
        "tokens": [int(token) for token in result.operator_ids],
        "score": float(base.get("score", 0.0)),
        "operator_names": list(result.operator_names),
        "termination_reason": result.termination_reason,
    }


def _candidate_artifact(row: dict) -> dict:
    return {
        "rank": int(row.get("rank", 0)),
        "tokens": [int(token) for token in row.get("tokens", [])],
        "score": row.get("score"),
        "train_index": row.get("train_index"),
        "lexical_score": row.get("lexical_score"),
        "task_type": row.get("task_type"),
        "operator_names": copy.deepcopy(row.get("operator_names", [])),
        "termination_reason": row.get("termination_reason"),
    }


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
        "exact_match": float(pred == ref),
        "length_ratio": round(len(pred) / len(ref), 6) if ref else 0.0,
        "length_accuracy": float(len(pred) == len(ref)),
        "abs_length_error": abs(len(pred) - len(ref)),
    }


def _aggregate_metrics(rows: Sequence[dict]) -> dict:
    keys = [
        "exact_match",
        "token_accuracy",
        "top5_sequence_accuracy",
        "lcs_ratio",
        "set_f1",
        "io_validity",
        "length_accuracy",
        "abs_length_error",
    ]
    out = {"n": len(rows)}
    for key in keys:
        out[key] = round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8)
    out["avg_abs_length_error"] = out.pop("abs_length_error")
    return out


def _aggregate_oracle(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    return {
        "mean_best_oracle_lcs_ratio": round(sum(float(row.get("best_oracle_lcs_ratio", 0.0)) for row in rows) / len(rows), 8),
        "mean_best_oracle_token_accuracy": round(sum(float(row.get("best_oracle_token_accuracy", 0.0)) for row in rows) / len(rows), 8),
        "reference_in_candidate_pool_rate": round(sum(1 for row in rows if row.get("reference_in_beam")) / len(rows), 8),
    }


def _aggregate_diversity(rows: Sequence[dict]) -> dict:
    keys = ["candidate_count", "unique_sequences", "unique_sequence_ratio", "avg_pairwise_lcs_distance", "avg_candidate_length"]
    return {key: round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8) for key in keys}


def _aggregate_attribution(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    return {
        "mean_copied_operator_ratio": round(sum(float(row.get("copied_operator_ratio", 0.0)) for row in rows) / len(rows), 8),
        "mean_novel_operator_ratio": round(sum(float(row.get("novel_operator_ratio", 0.0)) for row in rows) / len(rows), 8),
        "total_copied_operators": sum(int(row.get("copied_operator_count", 0)) for row in rows),
        "total_novel_operators": sum(int(row.get("novel_operator_count", 0)) for row in rows),
    }


def _topk_sequence_accuracy(candidates: Sequence[dict], reference: Sequence[int], *, k: int) -> float:
    ref = [int(token) for token in reference]
    return float(any([int(token) for token in row.get("tokens", [])] == ref for row in list(candidates)[: int(k)]))


def _basic_error_taxonomy(pred: Sequence[int], ref: Sequence[int]) -> list[str]:
    if list(pred) == list(ref):
        return ["exact_match"]
    categories = ["sequence_mismatch"]
    ratio = len(pred) / len(ref) if ref else 0.0
    if ratio < 0.67:
        categories.append("early_END")
    if ratio > 1.5:
        categories.append("overlong_chain")
    stats = _repetition_statistics(pred)
    if stats.get("max_run", 0) >= 3 or stats.get("repeated_bigram_events", 0) > 0:
        categories.append("repetitive_collapse")
    return categories


def _repetition_statistics(tokens: Sequence[int]) -> dict:
    if not tokens:
        return {
            "length": 0,
            "unique_count": 0,
            "unique_ratio": 0.0,
            "repeated_token_events": 0,
            "max_run": 0,
            "repeated_bigram_events": 0,
        }
    counts = Counter(int(token) for token in tokens)
    max_run = 1
    run = 1
    for prev, cur in zip(tokens, tokens[1:]):
        if int(cur) == int(prev):
            run += 1
        else:
            run = 1
        max_run = max(max_run, run)
    bigrams = Counter((int(left), int(right)) for left, right in zip(tokens, tokens[1:]))
    return {
        "length": len(tokens),
        "unique_count": len(counts),
        "unique_ratio": round(len(counts) / len(tokens), 6),
        "repeated_token_events": sum(count - 1 for count in counts.values() if count > 1),
        "max_run": max_run,
        "repeated_bigram_events": sum(count - 1 for count in bigrams.values() if count > 1),
    }


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


def _task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return " ".join(str(meta.get(key) or "") for key in ("task_type", "task_name", "task_description")).strip() or "unknown task"


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


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# V5_final Retrieval-Assisted Evaluation",
        "",
        f"Checkpoint: `{report.get('checkpoint_metadata', {}).get('checkpoint_path')}`",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Retrieval top-k: `{report.get('retrieval_top_k')}`",
        "",
        "## Metrics",
        "",
        "| Method | Exact | Token Acc | Top5 | LCS | SetF1 | IO Valid | Length Acc | AbsLenErr |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, metrics in report.get("metrics", {}).items():
        lines.append(
            "| `{method}` | {exact} | {token} | {top5} | {lcs} | {setf1} | {io} | {length} | {err} |".format(
                method=method,
                exact=metrics.get("exact_match"),
                token=metrics.get("token_accuracy"),
                top5=metrics.get("top5_sequence_accuracy"),
                lcs=metrics.get("lcs_ratio"),
                setf1=metrics.get("set_f1"),
                io=metrics.get("io_validity"),
                length=metrics.get("length_accuracy"),
                err=metrics.get("avg_abs_length_error"),
            )
        )
    attr = report.get("retrieval_generation_attribution", {})
    lines.extend(
        [
            "",
            "## Retrieval Attribution",
            "",
            f"- Mean copied operator ratio: `{attr.get('mean_copied_operator_ratio')}`",
            f"- Mean novel operator ratio: `{attr.get('mean_novel_operator_ratio')}`",
            "",
            "This prototype is eval-only and adds no trainable modules.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "stage1" / "checkpoints" / "best_model.pt")
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "retrieval_assisted")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--beam-width", type=int, default=5)
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_retrieval_assisted(
        checkpoint=args.checkpoint,
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix=args.transition_matrix,
        output_dir=args.output_dir,
        eval_samples=args.eval_samples,
        beam_width=args.beam_width,
        retrieval_top_k=args.retrieval_top_k,
        device=args.device,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
