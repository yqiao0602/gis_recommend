#!/usr/bin/env python3
"""Minimal V5_final inference entrypoint with auditable traces."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.models.v5_final import (  # noqa: E402
    IOMaskBuilder,
    build_v5_empirical_prediction_record,
    deterministic_task_embeddings,
    extract_diagnostic_graph,
    load_v5_final_model,
)


SCHEMA_VERSION = "gis_recommend.v5_final.prediction.v1"


def default_paths() -> dict[str, Path]:
    return {
        "checkpoint": OUTPUT_DIR / "v5_final_checkpoints" / "latest_model.pt",
        "transition_matrix": OUTPUT_DIR / "transition_allowed_next.json",
        "output": OUTPUT_DIR / "evaluation_reports" / "v5_final_prediction_smoke.json",
    }


def _load_token_names(path: Optional[Path]) -> dict[int, str]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        if "id_to_token" in payload and isinstance(payload["id_to_token"], dict):
            return {int(key): str(value) for key, value in payload["id_to_token"].items()}
        if "id_to_l3" in payload and isinstance(payload["id_to_l3"], dict):
            return {int(key): str(value) for key, value in payload["id_to_l3"].items()}
    return {}


def run_v5_final_inference(
    *,
    checkpoint_path: Path,
    output_path: Path,
    task_text: str,
    io_mask_builder: Optional[IOMaskBuilder] = None,
    token_names: Optional[dict[int, str]] = None,
    max_len: Optional[int] = None,
    beam_width: int = 1,
) -> dict:
    model, payload = load_v5_final_model(checkpoint_path, map_location="cpu")
    config = model.config
    task_embeddings = deterministic_task_embeddings(
        task_text,
        hidden_size=config.bert_hidden_size,
    )
    if io_mask_builder is None:
        io_mask_builder = IOMaskBuilder(
            vocab_size=config.vocab_size,
            end_token_id=config.resolved_end_token_id,
            blocked_token_ids={config.resolved_pad_token_id, config.start_token_id},
        )
    names = token_names or {}
    if beam_width > 1:
        beams = model.decode_beam(
            task_embeddings=task_embeddings,
            io_mask_builder=io_mask_builder,
            token_names=names,
            max_len=max_len,
            beam_width=beam_width,
        )
        result = beams[0]
        result.beam_candidates = [
            {
                "rank": rank,
                "tokens": beam.operator_ids,
                "score": beam.beam_candidates[0]["score"] if beam.beam_candidates else None,
                "termination_reason": beam.termination_reason,
            }
            for rank, beam in enumerate(beams)
        ]
    else:
        result = model.decode_greedy(
            task_embeddings=task_embeddings,
            io_mask_builder=io_mask_builder,
            token_names=names,
            max_len=max_len,
        )
    checkpoint_metadata = {
        "format_version": payload["provenance"]["format_version"],
        "model_version": payload["provenance"]["model_version"],
        "architecture": payload["provenance"]["architecture"],
        "checkpoint_path": str(checkpoint_path),
    }
    prediction = build_v5_empirical_prediction_record(
        sample_id="ad_hoc",
        decode_result=result,
        reference_tokens=[],
        retrieval_diagnostics={},
        checkpoint_metadata=checkpoint_metadata,
    )
    graph = extract_diagnostic_graph(
        operator_ids=result.operator_ids,
        alpha_trace=result.alpha_trace,
        io_mask_builder=io_mask_builder,
        token_names=names,
        threshold_tau=config.graph_threshold_tau,
    )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_text": task_text,
        "prediction": prediction,
        "diagnostic_graph": graph,
        "checkpoint_metadata": checkpoint_metadata,
        "runtime_contract": {
            "diagnostics_gate_execution": False,
            "checkpoint_loaded_strictly": True,
            "raw_checkpoint_fallback": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def main(argv: Optional[list[str]] = None) -> dict:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=defaults["checkpoint"])
    parser.add_argument("--out", type=Path, default=defaults["output"])
    parser.add_argument("--task-text", required=True)
    parser.add_argument("--transition-matrix", type=Path, default=defaults["transition_matrix"])
    parser.add_argument("--token-names", type=Path, default=None)
    parser.add_argument("--max-len", type=int, default=None)
    parser.add_argument("--beam-width", type=int, default=1)
    args = parser.parse_args(argv)

    model, payload = load_v5_final_model(args.checkpoint, map_location="cpu")
    config = model.config
    del model, payload
    io_mask_builder = None
    if args.transition_matrix.exists():
        io_mask_builder = IOMaskBuilder.from_transition_matrix(
            args.transition_matrix,
            vocab_size=config.vocab_size,
            end_token_id=config.resolved_end_token_id,
            blocked_token_ids={config.resolved_pad_token_id, config.start_token_id},
        )
    artifact = run_v5_final_inference(
        checkpoint_path=args.checkpoint,
        output_path=args.out,
        task_text=args.task_text,
        io_mask_builder=io_mask_builder,
        token_names=_load_token_names(args.token_names),
        max_len=args.max_len,
        beam_width=args.beam_width,
    )
    print(f"Wrote V5_final prediction artifact: {args.out}")
    return artifact


if __name__ == "__main__":
    main()
