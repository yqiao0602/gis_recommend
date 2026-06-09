#!/usr/bin/env python3
"""Full V5_final training/evaluation entrypoint.

This wrapper delegates execution to ``gis_recommend.training.train_v5``.  It is
kept intentionally thin so all runtime authority stays in the direct training
config and callables, while reports and diagnostics remain storage-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import TOTAL_VOCAB_SIZE  # noqa: E402
from gis_recommend.training.train_v5 import V5TrainConfig, train_v5  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=V5TrainConfig.data_path)
    parser.add_argument("--splits", type=Path, default=V5TrainConfig.splits_path)
    parser.add_argument("--checkpoint-dir", type=Path, default=V5TrainConfig.checkpoint_dir)
    parser.add_argument("--evaluation-report", type=Path, default=V5TrainConfig.evaluation_report_path)
    parser.add_argument("--transition-matrix", type=Path, default=V5TrainConfig.transition_matrix_path)
    parser.add_argument("--vocab-size", type=int, default=TOTAL_VOCAB_SIZE)
    parser.add_argument("--batch-size", type=int, default=V5TrainConfig.batch_size)
    parser.add_argument("--epochs", type=int, default=V5TrainConfig.num_epochs)
    parser.add_argument("--lr", type=float, default=V5TrainConfig.lr)
    parser.add_argument("--weight-decay", type=float, default=V5TrainConfig.weight_decay)
    parser.add_argument("--gradient-clip", type=float, default=V5TrainConfig.gradient_clip)
    parser.add_argument("--patience", type=int, default=V5TrainConfig.patience)
    parser.add_argument("--seed", type=int, default=V5TrainConfig.seed)
    parser.add_argument("--device", default=V5TrainConfig.device)
    parser.add_argument("--num-workers", type=int, default=V5TrainConfig.num_workers)
    parser.add_argument("--eval-samples", type=int, default=V5TrainConfig.eval_samples)
    parser.add_argument("--beam-width", type=int, default=V5TrainConfig.beam_width)
    parser.add_argument("--subset-size", type=int, default=None)
    parser.add_argument("--subset-preset", choices=("1k", "5k", "10k"), default=None)
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--max-val-batches", type=int, default=None)
    parser.add_argument("--d-model", type=int, default=V5TrainConfig.d_model)
    parser.add_argument("--d-key", type=int, default=V5TrainConfig.d_key)
    parser.add_argument("--layers", type=int, default=V5TrainConfig.n_layers)
    parser.add_argument("--heads", type=int, default=V5TrainConfig.n_heads)
    parser.add_argument("--d-ff", type=int, default=V5TrainConfig.d_ff)
    parser.add_argument("--bert-hidden-size", type=int, default=V5TrainConfig.bert_hidden_size)
    parser.add_argument("--max-seq-len", type=int, default=V5TrainConfig.max_seq_len)
    parser.add_argument("--dropout", type=float, default=V5TrainConfig.dropout)
    parser.add_argument("--io-bias-start", type=float, default=V5TrainConfig.io_bias_start)
    parser.add_argument("--io-bias-end", type=float, default=V5TrainConfig.io_bias_end)
    parser.add_argument("--io-bias-anneal-epochs", type=int, default=V5TrainConfig.io_bias_anneal_epochs)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--no-pvm", "--disable-pvm", dest="no_pvm", action="store_true")
    parser.add_argument("--no-qk-decoupling", action="store_true")
    parser.add_argument("--no-fixed-gamma", action="store_true")
    parser.add_argument("--no-alpha-noise", action="store_true")
    parser.add_argument("--greedy-decode-vs-beam", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    config = V5TrainConfig(
        data_path=args.data,
        splits_path=args.splits,
        checkpoint_dir=args.checkpoint_dir,
        evaluation_report_path=args.evaluation_report,
        transition_matrix_path=args.transition_matrix,
        vocab_size=args.vocab_size,
        d_model=args.d_model,
        d_key=args.d_key,
        n_layers=args.layers,
        n_heads=args.heads,
        d_ff=args.d_ff,
        bert_hidden_size=args.bert_hidden_size,
        max_seq_len=args.max_seq_len,
        dropout=args.dropout,
        batch_size=args.batch_size,
        num_epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        gradient_clip=args.gradient_clip,
        patience=args.patience,
        seed=args.seed,
        use_amp=not args.no_amp,
        num_workers=args.num_workers,
        device=args.device,
        subset_size=args.subset_size,
        subset_preset=args.subset_preset,
        dry_run=args.dry_run,
        eval_samples=args.eval_samples,
        beam_width=args.beam_width,
        max_train_batches=args.max_train_batches,
        max_val_batches=args.max_val_batches,
        no_pvm=args.no_pvm,
        no_qk_decoupling=args.no_qk_decoupling,
        no_fixed_gamma=args.no_fixed_gamma,
        no_alpha_noise=args.no_alpha_noise,
        greedy_decode_vs_beam=args.greedy_decode_vs_beam,
        io_bias_start=args.io_bias_start,
        io_bias_end=args.io_bias_end,
        io_bias_anneal_epochs=args.io_bias_anneal_epochs,
    )
    result = train_v5(config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
