#!/bin/bash
# V2a-P1 E1 formal training (gate 3; runs ONLY after eos-sanity + smoke PASS).
# Locked per spec 067a30a / owner ruling 2026-09-17:
#   lambda=20, 1 epoch, seed 20260916, microbatch 1 x accum 32, length-bucketed,
#   same A data / prompt / JSON schema as C0. NO ngram, NO repetition penalty,
#   NO canonicalization change. No mid-run tuning (pre-registered single-variable).
set -u
cd /home/qy/gee_llm_smoke
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_e1_train.log

echo "[E1] $(date) formal training start (lam=20, 1 epoch)" >> $LOG
$PY v2a_sft.py --model $M --train v2a_A_train.jsonl --dev v2a_A_dev.jsonl \
    --test v2a_A_test.jsonl --profile E1 --out-dir v2a_e1 \
    --eos-lambda 20 --length-bucketed --batch-size 1 --grad-accum 32 \
    >> $LOG 2>&1
echo "[E1] $(date) exit=$?" >> $LOG
echo "[E1] $(date) ALL DONE" >> $LOG
