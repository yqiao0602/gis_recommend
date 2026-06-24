#!/usr/bin/env python3
"""⚠️ DEPRECATED 2026-06-24 — 审查发现此方案不可用。

问题：通过重复 train index 做 20x 上采样，但 validate_split_indices 会拒绝
duplicate index。实测输出的 dataset_splits_v4_vector_v2_upsampled.json:
  train 258,767 行、唯一 index 67,209、重复 191,558。

正确做法：使用 step8_quality_gate_qgis_vector_oversampled（复制 workflow 行
+ 唯一 split index），或在 DataLoader sampler 层实现受控 sample weight。

本文件保留仅供参考，不得用于生成训练 splits。

（审查意见见 2026-06-24 用户代码审查。）
"""
import sys


if "--force-deprecated" not in sys.argv:
    raise SystemExit(
        "scripts/_upsample_splits.py 已弃用，默认不会生成重复-index split。\n"
        "当前 validate_split_indices 会拒绝 duplicate index；请改用 "
        "step8_quality_gate_qgis_vector_oversampled，或在 DataLoader sampler 层做权重采样。\n"
        "如果只是为了复现旧输出，必须显式加 --force-deprecated。"
    )

sys.argv.remove("--force-deprecated")

import json, random
from collections import Counter

# Load workflows
wf = json.load(open("outputs_v2/labeled_workflows_l3_v4_vector_v2.json", encoding="utf-8"))
samples = wf["labeled_workflows"]
n = len(samples)

# Find vector samples (contain L3_02 codes)
vector_indices = []
for i, s in enumerate(samples):
    codes = s.get("l3_codes", [])
    has_vec = any(c.startswith("L3_02") for c in codes if c not in ("<START>", "<END>"))
    if has_vec:
        vector_indices.append(i)

print(f"Total: {n}")
print(f"Vector: {len(vector_indices)} ({100*len(vector_indices)//n}%)")

# Generate splits
random.seed(42)
indices = list(range(n))
random.shuffle(indices)
n_train = int(n * 0.8)
n_val = int(n * 0.1)

train_base = sorted(indices[:n_train])
val_idx = sorted(indices[n_train:n_train+n_val])
test_idx = sorted(indices[n_train+n_val:])

# Find vector indices in train set
vec_in_train = [i for i in train_base if i in set(vector_indices)]
print(f"Vector in train base: {len(vec_in_train)}")

# Duplicate 20x
UPSAMPLE = 20
train_upsampled = []
for i in train_base:
    train_upsampled.append(i)
    if i in set(vector_indices):
        for _ in range(UPSAMPLE - 1):
            train_upsampled.append(i)

print(f"Train after 20x upsampling: {len(train_upsampled)} "
      f"(base={len(train_base)} + {len(vec_in_train)}×{UPSAMPLE-1})")
print(f"Effective vector ratio: {len(vec_in_train)*UPSAMPLE}/{len(train_upsampled)} "
      f"= {100*len(vec_in_train)*UPSAMPLE//len(train_upsampled)}%")

splits = {
    "train_indices": train_upsampled,
    "val_indices": val_idx,
    "test_indices": test_idx,
    "_stats": {
        "total": n,
        "n_train_base": len(train_base),
        "n_train_upsampled": len(train_upsampled),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "n_vector": len(vector_indices),
        "upsample_factor": UPSAMPLE,
    }
}

with open("outputs_v2/dataset_splits_v4_vector_v2_upsampled.json", "w", encoding="utf-8") as f:
    json.dump(splits, f, ensure_ascii=False)
print(f"\nSaved: dataset_splits_v4_vector_v2_upsampled.json")
