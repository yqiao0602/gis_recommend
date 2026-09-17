#!/bin/bash
# V2a-P1 formal evaluation: E1 adapter under the FROZEN protocol
# (greedy / 512 / explicit EOS stop, full-text predictions) then Protocol v2
# scoring (v2a_score.py) with canonicalization column.
# The in-training eval is NOT usable for the formal comparison (300-char raw,
# 1024-token cap); this chain is the only legitimate P1 comparison artifact.
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_e1_eval.log

echo "[E1eval] $(date) dev start" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_e1/adapter_v1 --data v2a_A_dev.jsonl \
    --out-dir v2a_e1 --tag dev --max-new-tokens 512 >> $LOG 2>&1
echo "[E1eval] $(date) dev exit=$?" >> $LOG
echo "[E1eval] $(date) test start" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_e1/adapter_v1 --data v2a_A_test.jsonl \
    --out-dir v2a_e1 --tag test --max-new-tokens 512 >> $LOG 2>&1
echo "[E1eval] $(date) test exit=$?" >> $LOG
# Protocol v2 scoring (CPU, offline, canonicalized column)
$PY v2a_score.py --predictions v2a_e1/v2a_dev_predictions.jsonl \
    --data v2a_A_dev.jsonl --out v2a_e1/v2a_dev_score_v2.json --canonicalize >> $LOG 2>&1
$PY v2a_score.py --predictions v2a_e1/v2a_test_predictions.jsonl \
    --data v2a_A_test.jsonl --out v2a_e1/v2a_test_score_v2.json --canonicalize >> $LOG 2>&1
echo "[E1eval] $(date) ALL DONE" >> $LOG
