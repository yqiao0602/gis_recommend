#!/bin/bash
# V2a evaluation chain: identical eval script + identical decoding for A and B.
# Runs back-to-back so no human polling is needed between stages.
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_eval_chain.log

run() {  # run <adapter> <data> <tag> <outdir>
  echo "=== $(date) START $3 ($2) ===" >> $LOG
  $PY v2a_eval.py --model $M --adapter "$1" --data "$2" \
      --out-dir "$4" --tag "$3" --max-new-tokens 512 >> $LOG 2>&1
  echo "=== $(date) END $3 rc=$? ===" >> $LOG
}

mkdir -p v2a_a v2a_b
run v2a_a/adapter_v1 v2a_A_dev.jsonl  dev_a  v2a_a
run v2a_b/adapter_v1 v2a_B_dev.jsonl  dev_b  v2a_b
run v2a_a/adapter_v1 v2a_A_test.jsonl test_a v2a_a
run v2a_b/adapter_v1 v2a_B_test.jsonl test_b v2a_b
echo "=== $(date) CHAIN COMPLETE ===" >> $LOG
