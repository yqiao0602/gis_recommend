#!/usr/bin/env python3
"""Pre-flight guard: validates vocab/profile consistency before training/eval.

Checks:
    - VOCAB_SIZE vs id_mappings L3 count
    - Training data max token vs VOCAB_SIZE
    - Set Predictor active tokens vs VOCAB_SIZE
    - Checkpoint output head dimension vs VOCAB_SIZE (if checkpoint exists)

Returns exit code 0 if all checks pass, 1 if any fail.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import gis_recommend.config.transformer_config as cfg  # noqa: E402
from gis_recommend.config.vocab_profile import (  # noqa: E402
    VocabProfileError,
    apply_profile,
    current_profile,
    V3_107_EXPERIMENTAL,
)


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_id_mappings(id_mappings_path: str) -> list[str]:
    errors = []
    if not Path(id_mappings_path).exists():
        errors.append(f"ID mappings not found: {id_mappings_path}")
        return errors
    mappings = _load_json(id_mappings_path)
    l3 = mappings.get("l3", {})
    l3_count = len(l3)
    if l3_count != cfg.VOCAB_SIZE:
        errors.append(
            f"VOCAB_SIZE={cfg.VOCAB_SIZE} but id_mappings has {l3_count} L3 codes"
        )
    return errors


def check_training_data(data_path: str) -> list[str]:
    errors = []
    if not Path(data_path).exists():
        errors.append(f"Training data not found: {data_path}")
        return errors
    data = _load_json(data_path)
    wfs = data.get("labeled_workflows", data) if isinstance(data, dict) else data
    if not isinstance(wfs, list):
        errors.append("Training data labeled_workflows is not a list")
        return errors
    max_tok = -1
    for wf in wfs:
        if isinstance(wf, dict):
            for t in wf.get("l3_sequence", []):
                if isinstance(t, int) and t > max_tok:
                    max_tok = t
    if max_tok >= cfg.VOCAB_SIZE:
        errors.append(
            f"Training data max token {max_tok} >= VOCAB_SIZE {cfg.VOCAB_SIZE}"
        )
    return errors


def check_set_predictor(sp_dir: str) -> list[str]:
    errors = []
    sp_path = Path(sp_dir) / "best_model.pth"
    if not sp_path.exists():
        # Set Predictor may not be trained yet — non-fatal
        return errors
    import torch  # noqa: E402
    ck = torch.load(str(sp_path), map_location="cpu", weights_only=True)
    active = ck.get("active_token_ids", [])
    if active:
        max_active = max(active)
        if max_active >= cfg.VOCAB_SIZE:
            errors.append(
                f"Set Predictor active token {max_active} >= VOCAB_SIZE {cfg.VOCAB_SIZE}"
            )
    return errors


def check_checkpoint(ckpt_path: str) -> list[str]:
    errors = []
    if not Path(ckpt_path).exists():
        return errors  # from-scratch training won't have a checkpoint yet
    import torch  # noqa: E402
    ck = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    sd = ck.get("model_state_dict", {})
    # Check L3 output projection head
    for key in ["l3_head.weight", "output_proj.weight", "lm_head.weight"]:
        w = sd.get(key)
        if w is not None:
            if w.shape[0] != cfg.VOCAB_SIZE:
                errors.append(
                    f"Checkpoint {key} shape[0]={w.shape[0]} != VOCAB_SIZE={cfg.VOCAB_SIZE}"
                )
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=None,
                        help="Vocab profile to check (default: current active)")
    parser.add_argument("--id-mappings", default=None)
    parser.add_argument("--data", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--set-predictor", default=None)
    args = parser.parse_args()

    if args.profile:
        try:
            apply_profile(args.profile)
        except VocabProfileError as e:
            print(f"[PREFLIGHT] FAIL: {e}")
            return 1

    profile_name = current_profile()
    print(f"[PREFLIGHT] Profile: {profile_name}, VOCAB_SIZE={cfg.VOCAB_SIZE}")

    all_errors: list[str] = []

    if args.id_mappings:
        all_errors.extend(check_id_mappings(args.id_mappings))
    if args.data:
        all_errors.extend(check_training_data(args.data))
    if args.checkpoint:
        all_errors.extend(check_checkpoint(args.checkpoint))
    if args.set_predictor:
        all_errors.extend(check_set_predictor(args.set_predictor))

    if all_errors:
        print(f"[PREFLIGHT] FAIL ({len(all_errors)} error(s)):")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("[PREFLIGHT] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
