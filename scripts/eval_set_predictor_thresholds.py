# -*- coding: utf-8 -*-
"""
评估 Set Predictor 在不同 confidence threshold 下的 Precision/Recall/F1。
不需要重新训练，直接加载 best checkpoint 跑推理。

用法:
    python scripts/eval_set_predictor_thresholds.py
"""

import json
import sys
import torch
from pathlib import Path
from collections import Counter
from transformers import BertTokenizer

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gis_recommend.config.transformer_config import (
    OUTPUT_DIR, DEVICE,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    SET_PREDICTOR_CHECKPOINT_DIR, SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
    SET_PREDICTOR_CONFIDENCE_THRESHOLD,
)
from gis_recommend.models.set_predictor_v3 import L3SetPredictor
from gis_recommend.training.train_set_predictor_v3 import (
    SetPredictorDataset, compute_metrics, load_or_create_splits,
)

def main():
    print("=" * 70)
    print("Set Predictor Multi-Threshold Evaluation")
    print("=" * 70)

    # Load data — use same path as training
    data_path = V4_LABELED_WORKFLOWS_PATH
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    workflows = data['labeled_workflows'] if isinstance(data, dict) and 'labeled_workflows' in data else data
    print(f"Loaded {len(workflows)} workflows")

    with open(V4_TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
        task_type_vocab = json.load(f)

    # Load model first so active_token_ids always match the checkpoint
    model_path = SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
    model = L3SetPredictor.from_checkpoint(str(model_path), device=DEVICE)
    model.eval()
    active_token_ids = model.active_token_ids.cpu().tolist()
    print(f"Model loaded from {model_path}")
    print(f"Active tokens from checkpoint: {len(active_token_ids)}")

    # Split — reuse existing splits
    split_path = OUTPUT_DIR / "dataset_splits_v4.json"
    splits = load_or_create_splits(workflows, split_path)
    test_wfs = [workflows[i] for i in splits['test_indices']]
    print(f"Test set: {len(test_wfs)} samples")

    # Dataset & loader
    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    test_ds = SetPredictorDataset(
        test_wfs, active_token_ids, task_type_vocab, bert_tokenizer,
        num_count_classes=model.num_count_classes,
    )
    test_loader = torch.utils.data.DataLoader(
        test_ds, batch_size=64, shuffle=False, num_workers=0, pin_memory=True
    )

    # Collect all predictions
    all_binary_logits = []
    all_count_logits = []
    all_binary_targets = []
    all_count_targets = []

    with torch.no_grad():
        for batch in test_loader:
            task_type_ids = batch['task_type_id'].to(DEVICE)
            text_input_ids = batch['text_input_ids'].to(DEVICE)
            text_attention_mask = batch['text_attention_mask'].to(DEVICE)
            binary_targets = batch['binary_targets'].to(DEVICE)
            count_targets = batch['count_targets'].to(DEVICE)

            binary_logits, count_logits = model(
                task_type_ids, text_input_ids, text_attention_mask
            )
            all_binary_logits.append(binary_logits.cpu())
            all_count_logits.append(count_logits.cpu())
            all_binary_targets.append(binary_targets.cpu())
            all_count_targets.append(count_targets.cpu())

    all_bl = torch.cat(all_binary_logits, dim=0)
    all_cl = torch.cat(all_count_logits, dim=0)
    all_bt = torch.cat(all_binary_targets, dim=0)
    all_ct = torch.cat(all_count_targets, dim=0)

    print(f"\nCollected predictions: {all_bl.shape[0]} samples, {all_bl.shape[1]} tokens")

    # Multi-threshold evaluation
    thresholds = sorted({
        0.3, 0.4, 0.5, 0.55, 0.6,
        float(SET_PREDICTOR_SOFT_PRIOR_THRESHOLD),
        0.75,
        float(SET_PREDICTOR_CONFIDENCE_THRESHOLD),
        0.85, 0.9, 0.95,
    })

    print(f"\n{'Threshold':>10} | {'Precision':>10} | {'Recall':>10} | {'F1':>10} | {'AvgPredSize':>12} | {'CntAcc':>8} | {'CntMAE':>8}")
    print("-" * 85)

    best_f1 = 0
    best_thr = 0
    best_p70_thr = None  # threshold where precision first >= 70%

    for thr in thresholds:
        m = compute_metrics(all_bl, all_cl, all_bt, all_ct, threshold=thr)
        markers = []
        if abs(thr - SET_PREDICTOR_SOFT_PRIOR_THRESHOLD) < 1e-8:
            markers.append("soft-prior")
        if abs(thr - SET_PREDICTOR_CONFIDENCE_THRESHOLD) < 1e-8:
            markers.append("hard-threshold")
        marker = f" ← {', '.join(markers)}" if markers else ""
        if m['set_f1'] > best_f1:
            best_f1 = m['set_f1']
            best_thr = thr
        if best_p70_thr is None and m['set_precision'] >= 0.70:
            best_p70_thr = thr

        print(f"  {thr:>8.2f} | {m['set_precision']:>10.4f} | {m['set_recall']:>10.4f} | "
              f"{m['set_f1']:>10.4f} | {m['avg_pred_size']:>12.1f} | "
              f"{m['count_acc']:>8.4f} | {m['count_mae']:>8.4f}{marker}")

    print("-" * 85)
    print(f"Best F1 = {best_f1:.4f} at threshold = {best_thr}")
    if best_p70_thr is not None:
        print(f"Precision >= 70% first at threshold = {best_p70_thr}")
    else:
        print(f"Precision never reaches 70% in tested range")

    analysis_threshold = float(SET_PREDICTOR_SOFT_PRIOR_THRESHOLD)

    # Per-sample analysis at soft-prior threshold
    print(f"\n{'='*70}")
    print(f"Per-sample error analysis (threshold={analysis_threshold:.2f})")
    print(f"{'='*70}")

    binary_probs = torch.sigmoid(all_bl)
    pred_present = (binary_probs > analysis_threshold)
    true_present = (all_bt > 0.5)

    tp = (pred_present & true_present).float().sum(dim=1)
    fp = (pred_present & ~true_present).float().sum(dim=1)
    fn = (~pred_present & true_present).float().sum(dim=1)

    pred_sizes = pred_present.float().sum(dim=1)
    true_sizes = true_present.float().sum(dim=1)

    print(f"Average true set size: {true_sizes.mean():.1f}")
    print(f"Average pred set size: {pred_sizes.mean():.1f}")
    print(f"Average TP per sample: {tp.mean():.1f}")
    print(f"Average FP per sample: {fp.mean():.1f}")
    print(f"Average FN per sample: {fn.mean():.1f}")

    # Distribution of FP counts
    fp_counts = Counter(fp.int().tolist())
    print(f"\nFalse Positive distribution:")
    for n_fp in sorted(fp_counts.keys())[:10]:
        count = fp_counts[n_fp]
        print(f"  {n_fp} FP: {count} samples ({count/len(test_wfs)*100:.1f}%)")


if __name__ == '__main__':
    main()
