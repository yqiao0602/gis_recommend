#!/bin/bash
# Follow-up after the dev chain: run the two TEST evaluations with the same
# script and decoding as the dev runs, so all four share one metric contract.
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
MODEL=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_eval_test_chain.log

echo "[test-chain] $(date) waiting for dev chain to finish"
while pgrep -f 'bash v2a_eval_chain.sh' >/dev/null 2>&1; do sleep 60; done
while pgrep -f 'python v2a_eval.py' >/dev/null 2>&1; do sleep 30; done
sleep 20
echo "[test-chain] $(date) dev chain done; A test eval"
$PY v2a_eval.py --model $MODEL --adapter v2a_a/adapter_v1 \
    --data v2a_A_test.jsonl --out-dir v2a_a --tag test --max-new-tokens 512 \
    > v2a_a_test_eval.log 2>&1
echo "[test-chain] $(date) A test exit=$?"
echo "[test-chain] $(date) B test eval"
$PY v2a_eval.py --model $MODEL --adapter v2a_b/adapter_v1 \
    --data v2a_B_test.jsonl --out-dir v2a_b --tag test --max-new-tokens 512 \
    > v2a_b_test_eval.log 2>&1
echo "[test-chain] $(date) B test exit=$?"
echo "[test-chain] $(date) ALL DONE"
