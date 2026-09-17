#!/bin/bash
# V2a termination-control full dev rerun (A adapter, 120 rows).
# Config chosen from the 8-row smoke series (2026-09-17):
#   - no_repeat_ngram_size=8 only: stops long-runaway repetition without
#     breaking JSON structure, and is the ONLY variant that did not zero out
#     operator F1 on the smoke set
#   - repetition_penalty (1.1/1.15) REJECTED by smoke: it suppresses the
#     shared native:/gdal: prefix tokens and collapsed operator F1 to 0
# Baseline for comparison: v2a_dev_canon_eval_metrics.json (frozen protocol,
# full-text predictions, same committed metric code).
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_term_dev.log

echo "[term] $(date) A dev ngram8-only start" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_a/adapter_v1 --data v2a_A_dev.jsonl \
    --out-dir v2a_a --tag dev_n8only --max-new-tokens 512 \
    --no-repeat-ngram-size 8 --canonicalize >> $LOG 2>&1
echo "[term] $(date) exit=$?" >> $LOG
echo "[term] $(date) ALL DONE" >> $LOG
