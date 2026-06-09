# -*- coding: utf-8 -*-
"""
Analyze: Does the configured threshold produce the same token set as top-K=8?

For each test sample (first 100), compare:
  - threshold mode: all tokens with sigmoid > configured threshold
  - top-K mode: top 8 tokens by sigmoid probability

Reports:
  1. Exact match ratio
  2. Per-sample diff (tokens added/removed by top-K vs threshold)
  3. Sigmoid probability distribution stats (top-8 avg vs rank 9-15 avg)

Usage:
    python scripts/analyze_threshold_vs_topk.py
"""

import json
import sys
from pathlib import Path

import torch
from transformers import BertTokenizer

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gis_recommend.config.transformer_config import (
    OUTPUT_DIR, DEVICE,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    SET_PREDICTOR_CHECKPOINT_DIR, SET_PREDICTOR_CONFIDENCE_THRESHOLD,
)
from gis_recommend.models.set_predictor_v3 import L3SetPredictor
from gis_recommend.training.train_set_predictor_v3 import (
    SetPredictorDataset, load_or_create_splits,
)


def main():
    print("=" * 70)
    print(f"Threshold={SET_PREDICTOR_CONFIDENCE_THRESHOLD:.2f} vs Top-K=8: Token Set Comparison")
    print("=" * 70)

    # ── Load data ──
    print("\n[1] Loading data...")
    with open(V4_LABELED_WORKFLOWS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    workflows = data['labeled_workflows'] if isinstance(data, dict) and 'labeled_workflows' in data else data
    print(f"  Loaded {len(workflows)} workflows")

    with open(V4_TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
        task_type_vocab = json.load(f)

    # Load model first so active_token_ids always match the checkpoint
    print("\n[2] Loading model...")
    model_path = SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
    model = L3SetPredictor.from_checkpoint(str(model_path), device=DEVICE)
    model.eval()
    print(f"  Model loaded from {model_path}")
    print(f"  Active tokens: {model.num_active_tokens}")
    active_token_ids = model.active_token_ids.cpu().tolist()

    # Split
    split_path = OUTPUT_DIR / "dataset_splits_v4.json"
    splits = load_or_create_splits(workflows, split_path)
    test_wfs = [workflows[i] for i in splits['test_indices']]
    print(f"  Test set: {len(test_wfs)} samples")

    # Use first 100 samples
    N_SAMPLES = min(100, len(test_wfs))
    test_wfs_subset = test_wfs[:N_SAMPLES]
    print(f"  Using first {N_SAMPLES} samples for analysis")

    # ── Build dataset and loader ──
    print("\n[3] Building dataset...")
    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    test_ds = SetPredictorDataset(
        test_wfs_subset, active_token_ids, task_type_vocab, bert_tokenizer,
        num_count_classes=model.num_count_classes,
    )
    test_loader = torch.utils.data.DataLoader(
        test_ds, batch_size=64, shuffle=False, num_workers=0, pin_memory=True
    )

    # ── Collect raw sigmoid probabilities ──
    print("\n[4] Running inference...")
    all_binary_logits = []
    all_binary_targets = []

    with torch.no_grad():
        for batch in test_loader:
            task_type_ids = batch['task_type_id'].to(DEVICE)
            text_input_ids = batch['text_input_ids'].to(DEVICE)
            text_attention_mask = batch['text_attention_mask'].to(DEVICE)
            binary_targets = batch['binary_targets'].to(DEVICE)

            binary_logits, _ = model(
                task_type_ids, text_input_ids, text_attention_mask
            )
            all_binary_logits.append(binary_logits.cpu())
            all_binary_targets.append(binary_targets.cpu())

    all_bl = torch.cat(all_binary_logits, dim=0)  # [N_SAMPLES, num_active]
    all_bt = torch.cat(all_binary_targets, dim=0)
    all_probs = torch.sigmoid(all_bl)  # [N_SAMPLES, num_active]

    print(f"  Predictions shape: {all_probs.shape}")

    # ── Compare threshold vs top-K=8 ──
    print("\n" + "=" * 70)
    print(f"[5] Comparing threshold={SET_PREDICTOR_CONFIDENCE_THRESHOLD:.2f} vs top-K=8")
    print("=" * 70)

    THRESHOLD = float(SET_PREDICTOR_CONFIDENCE_THRESHOLD)
    K = 8

    active_ids = model.active_token_ids.cpu().numpy()

    exact_match_count = 0
    topk_extra_tokens_all = []    # tokens in top-K but NOT in threshold set
    topk_missing_tokens_all = []  # tokens in threshold set but NOT in top-K
    threshold_sizes = []
    topk_sizes = []

    # Per-sample probability stats
    top8_avg_probs = []
    rank9_15_avg_probs = []
    all_sorted_probs = []

    diff_samples = []  # store details of differing samples

    for i in range(N_SAMPLES):
        probs = all_probs[i]  # [num_active]
        targets = all_bt[i]

        # Threshold mode: sigmoid > configured threshold
        threshold_mask = probs > THRESHOLD
        threshold_indices = set(threshold_mask.nonzero(as_tuple=True)[0].tolist())

        # Top-K mode: top 8 by probability
        topk_probs, topk_idx = probs.topk(K)
        topk_indices = set(topk_idx.tolist())

        threshold_sizes.append(len(threshold_indices))
        topk_sizes.append(len(topk_indices))

        # Check exact match
        if threshold_indices == topk_indices:
            exact_match_count += 1
        else:
            # Compute diff
            extra_in_topk = topk_indices - threshold_indices  # in top-K but below threshold
            missing_from_topk = threshold_indices - topk_indices  # above threshold but not in top-K
            topk_extra_tokens_all.append(extra_in_topk)
            topk_missing_tokens_all.append(missing_from_topk)

            diff_samples.append({
                'sample_idx': i,
                'threshold_size': len(threshold_indices),
                'topk_size': K,
                'extra_in_topk': [(active_ids[j], probs[j].item()) for j in sorted(extra_in_topk)],
                'missing_from_topk': [(active_ids[j], probs[j].item()) for j in sorted(missing_from_topk)],
            })

        # Probability distribution stats
        sorted_probs, _ = probs.sort(descending=True)
        all_sorted_probs.append(sorted_probs)
        top8_avg_probs.append(sorted_probs[:8].mean().item())
        if sorted_probs.size(0) >= 15:
            rank9_15_avg_probs.append(sorted_probs[8:15].mean().item())
        else:
            rank9_15_avg_probs.append(sorted_probs[8:].mean().item())

    # ── Report ──
    print(f"\n--- Result Summary ---")
    print(f"  Samples analyzed: {N_SAMPLES}")
    print(f"  Exact match (same token set): {exact_match_count}/{N_SAMPLES} = {exact_match_count/N_SAMPLES*100:.1f}%")
    print(f"  Different: {N_SAMPLES - exact_match_count}/{N_SAMPLES} = {(N_SAMPLES - exact_match_count)/N_SAMPLES*100:.1f}%")

    print(f"\n--- Set Size Statistics ---")
    import numpy as np
    thr_sizes = np.array(threshold_sizes)
    topk_sizes_arr = np.array(topk_sizes)
    print(f"  Threshold={THRESHOLD:.2f} set sizes: mean={thr_sizes.mean():.1f}, median={np.median(thr_sizes):.0f}, "
          f"min={thr_sizes.min()}, max={thr_sizes.max()}, std={thr_sizes.std():.1f}")
    print(f"  Top-K=8 set sizes: always {K} (by definition)")

    # Distribution of threshold set sizes
    from collections import Counter
    size_dist = Counter(threshold_sizes)
    print(f"\n  Threshold={THRESHOLD:.2f} set size distribution:")
    for sz in sorted(size_dist.keys()):
        cnt = size_dist[sz]
        bar = "#" * cnt
        print(f"    size={sz:2d}: {cnt:3d} samples  {bar}")

    print(f"\n--- Probability Distribution ---")
    top8_arr = np.array(top8_avg_probs)
    r9_15_arr = np.array(rank9_15_avg_probs)
    print(f"  Top-8 avg probability:    mean={top8_arr.mean():.4f}, std={top8_arr.std():.4f}")
    print(f"  Rank 9-15 avg probability: mean={r9_15_arr.mean():.4f}, std={r9_15_arr.std():.4f}")
    print(f"  Gap (top8 - rank9_15):     mean={top8_arr.mean() - r9_15_arr.mean():.4f}")

    # Show detailed probability profile for a few samples
    print(f"\n--- Per-Rank Probability Profile (averaged over {N_SAMPLES} samples) ---")
    # Stack all sorted probs
    max_show = 20
    stacked = torch.stack(all_sorted_probs, dim=0)  # [N_SAMPLES, num_active]
    mean_by_rank = stacked[:, :max_show].mean(dim=0)
    std_by_rank = stacked[:, :max_show].std(dim=0)
    print(f"  {'Rank':>5} | {'Mean Prob':>10} | {'Std':>10} | {f'> {THRESHOLD:.2f}':>8}")
    print(f"  " + "-" * 45)
    for r in range(max_show):
        above_thr = (stacked[:, r] > THRESHOLD).float().mean().item()
        marker = " <--- threshold cutoff" if r == 7 else ""
        if r == 8:
            marker = " <--- K=8 boundary"
        print(f"  {r+1:>5} | {mean_by_rank[r]:.6f}   | {std_by_rank[r]:.6f}   | {above_thr*100:>6.1f}%{marker}")

    # Show diff details (first 15 differing samples)
    if diff_samples:
        print(f"\n--- Detailed Diffs (first 15 of {len(diff_samples)} differing samples) ---")
        for d in diff_samples[:15]:
            idx = d['sample_idx']
            thr_sz = d['threshold_size']
            print(f"\n  Sample #{idx}: threshold selected {thr_sz} tokens, top-K selects {K}")
            if d['extra_in_topk']:
                print(f"    Top-K has but threshold DOESN'T (below threshold):")
                for tid, p in d['extra_in_topk']:
                    print(f"      token {tid}: prob={p:.4f}")
            if d['missing_from_topk']:
                print(f"    Threshold has but top-K DOESN'T (above threshold but outside top-8):")
                for tid, p in d['missing_from_topk']:
                    print(f"      token {tid}: prob={p:.4f}")

    # ── Analysis: Why they differ ──
    print(f"\n--- Root Cause Analysis ---")
    n_thr_smaller = sum(1 for s in threshold_sizes if s < K)
    n_thr_equal = sum(1 for s in threshold_sizes if s == K)
    n_thr_larger = sum(1 for s in threshold_sizes if s > K)
    print(f"  Threshold set < 8 tokens: {n_thr_smaller} samples ({n_thr_smaller/N_SAMPLES*100:.1f}%)")
    print(f"  Threshold set = 8 tokens: {n_thr_equal} samples ({n_thr_equal/N_SAMPLES*100:.1f}%)")
    print(f"  Threshold set > 8 tokens: {n_thr_larger} samples ({n_thr_larger/N_SAMPLES*100:.1f}%)")
    print(f"\n  When threshold selects exactly 8 tokens, they may still differ from top-K")
    print(f"  if the 8th-highest prob token is below threshold or a lower-ranked token is above threshold.")

    # For exact-8 threshold samples, check if they're always same as top-K
    exact8_match = 0
    exact8_total = 0
    for i in range(N_SAMPLES):
        if threshold_sizes[i] == K:
            exact8_total += 1
            probs = all_probs[i]
            threshold_mask = probs > THRESHOLD
            threshold_indices = set(threshold_mask.nonzero(as_tuple=True)[0].tolist())
            _, topk_idx = probs.topk(K)
            topk_indices = set(topk_idx.tolist())
            if threshold_indices == topk_indices:
                exact8_match += 1
    if exact8_total > 0:
        print(f"\n  Among {exact8_total} samples where threshold also selects 8: "
              f"{exact8_match} match top-K ({exact8_match/exact8_total*100:.1f}%)")

    # Check: what fraction of rank-8 tokens are above/below threshold?
    rank8_probs = stacked[:, 7]  # 0-indexed: rank 8
    rank9_probs = stacked[:, 8]  # rank 9
    print(f"\n  Rank-8 token prob: mean={rank8_probs.mean():.4f}, "
          f"above threshold: {(rank8_probs > THRESHOLD).float().mean()*100:.1f}%")
    print(f"  Rank-9 token prob: mean={rank9_probs.mean():.4f}, "
          f"above threshold: {(rank9_probs > THRESHOLD).float().mean()*100:.1f}%")

    print(f"\n{'='*70}")
    print("Analysis complete.")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
