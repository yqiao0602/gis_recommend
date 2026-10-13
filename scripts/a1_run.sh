#!/bin/bash
# A1 decode contrast — one-command execution on mdzhang (frozen protocol).
# Gate: adapter SHA already verified (A1_SHA_GATE_V1.json, PASS 2026-10-12).
# Prereq: >=9.5GiB free GPU memory (check: nvidia-smi --query-gpu=memory.free).
set -e
cd /home/qy/a1
PY=/home/qy/miniconda3/envs/qwen35/bin/python
BASE=/home/qy/models/Qwen3.5/Qwen3.5-9B-Base
ADAPTER=/home/qy/planner_v2_adapter_staging
DEV=/home/qy/a1/planner_v2_dev_fix1_loopinv.jsonl
SAMPLE=/home/qy/a1/A1_SAMPLE_131.json
OUT=/home/qy/a1/results_$(date +%Y%m%d_%H%M%S)

FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo "GPU free: ${FREE} MiB"
if [ "$FREE" -lt 9500 ]; then echo "ABORT: <9500 MiB free"; exit 1; fi

# dry-run gate (fingerprints base+adapter, validates sample; no GPU load)
$PY run_a1_decode_contrast_v1.py --base $BASE --adapter $ADAPTER \
  --dev $DEV --sample $SAMPLE --out-dir ${OUT}_dryrun --dry-run

# real run (nohup-safe; both arms 768 + 2048, single variable per protocol)
nohup $PY run_a1_decode_contrast_v1.py --base $BASE --adapter $ADAPTER \
  --dev $DEV --sample $SAMPLE --out-dir $OUT > a1_run.log 2>&1 &
echo "launched PID $! -> $OUT (log: /home/qy/a1/a1_run.log)"
