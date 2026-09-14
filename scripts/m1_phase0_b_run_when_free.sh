#!/bin/bash
# Phase 0-B auto-launch v2: waits until the GPU has NO compute processes
# (confirmed twice, 60 s apart), then runs the task_type 2x2 ablation.
# v1 failed by launching on a transient free-memory dip during the user's
# training run and on a wrong --taxonomy default; both are fixed here.
set -u
cd /home/qy/gee_llm_smoke
mkdir -p m1_phase0_b

echo "[wrapper] $(date) waiting for an idle GPU (no compute processes, double-confirmed)"
while true; do
  n_apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c .)
  if [ "$n_apps" -eq 0 ]; then
    sleep 60
    n_apps2=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c .)
    if [ "$n_apps2" -eq 0 ]; then
      echo "[wrapper] $(date) GPU idle confirmed; launching"
      break
    fi
  fi
  echo "[wrapper] $(date) compute processes on GPU: $n_apps"
  sleep 120
done

source /home/qy/miniconda3/etc/profile.d/conda.sh
conda activate qwen35
export GIS_VOCAB_PROFILE=paper_v1_128
export HF_HUB_OFFLINE=1
echo "[wrapper] $(date) launching Phase 0-B ablation"
python m1_phase0_b_tasktype_ablation.py \
  --checkpoint /home/qy/gee_llm_smoke/m1_r1_ckpt/best_gen_composite_model.pth \
  --out-dir /home/qy/gee_llm_smoke/m1_phase0_b 2>&1 | tee m1_phase0_b/run.log
echo "[wrapper] $(date) done"
