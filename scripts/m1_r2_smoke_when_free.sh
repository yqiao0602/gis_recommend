#!/bin/bash
# M1-R2 Phase 2-B smoke: waits for an idle GPU (no compute processes,
# double-confirmed 60s apart), then runs the 100-step DAPT smoke.
set -u
cd /home/qy/gee_llm_smoke
echo "[wrapper] $(date) waiting for idle GPU"
while true; do
  n=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c .)
  if [ "$n" -eq 0 ]; then
    sleep 60
    n2=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c .)
    if [ "$n2" -eq 0 ]; then break; fi
  fi
  sleep 120
done
source /home/qy/miniconda3/etc/profile.d/conda.sh
conda activate qwen35
export HF_HUB_OFFLINE=1
echo "[wrapper] $(date) launching M1-R2 DAPT smoke - 100 steps"
python m1_r2_dapt.py smoke --steps 100 --out /home/qy/gee_llm_smoke/m1_r2_dapt_smoke
echo "[wrapper] $(date) smoke done"
