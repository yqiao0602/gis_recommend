#!/bin/bash
# Re-run both dev evals with --canonicalize (adds the diagnostic block) AND
# full-text predictions (the earlier 400-char cut made re-scoring impossible).
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_recanon_chain.log

echo "[recanon] $(date) A dev" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_a/adapter_v1 --data v2a_A_dev.jsonl \
    --out-dir v2a_a --tag dev_canon --max-new-tokens 512 --canonicalize >> $LOG 2>&1
echo "[recanon] $(date) A dev exit=$?" >> $LOG
echo "[recanon] $(date) B dev" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_b/adapter_v1 --data v2a_B_dev.jsonl \
    --out-dir v2a_b --tag dev_canon --max-new-tokens 512 --canonicalize >> $LOG 2>&1
echo "[recanon] $(date) B dev exit=$?" >> $LOG
echo "[recanon] $(date) ALL DONE" >> $LOG
