#!/bin/bash
# V2a-P2 Gate D: formal C0-vs-P2 comparison run (frozen checkpoint, frozen
# protocol; ONLY variable = xgrammar grammar+catalog mask). No retraining.
# Gate C must have PASSED before this launches (spec 0078b82 §4).
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_p2_eval.log

echo "[P2] $(date) dev start" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_a/adapter_v1 --data v2a_A_dev.jsonl \
    --out-dir v2a_p2 --tag dev --max-new-tokens 512 --constrained >> $LOG 2>&1
rc=$?
echo "[P2] dev exit=$rc ($(date))" >> $LOG
echo "[P2] $(date) test start" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_a/adapter_v1 --data v2a_A_test.jsonl \
    --out-dir v2a_p2 --tag test --max-new-tokens 512 --constrained >> $LOG 2>&1
rc=$?
echo "[P2] test exit=$rc ($(date))" >> $LOG
$PY v2a_score.py --predictions v2a_p2/v2a_dev_predictions.jsonl \
    --data v2a_A_dev.jsonl --out v2a_p2/v2a_dev_score_v2.json --canonicalize >> $LOG 2>&1
$PY v2a_score.py --predictions v2a_p2/v2a_test_predictions.jsonl \
    --data v2a_A_test.jsonl --out v2a_p2/v2a_test_score_v2.json --canonicalize >> $LOG 2>&1
echo "[P2] $(date) ALL DONE" >> $LOG
