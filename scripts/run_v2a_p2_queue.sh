#!/bin/bash
# V2a-P2 queue: wait for the owner's route2 training (PID arg) to release the
# GPU, then run gate C (8-row constrained smoke), mechanically verify the spec
# pass criteria, and only then run gate D (formal dev+test). Single instance.
set -u
PID_TO_WAIT=${1:?usage: run_v2a_p2_queue.sh <route2_pid>}
cd /home/qy/gee_llm_smoke
PY=/home/qy/miniconda3/envs/qwen35/bin/python
M=/home/qy/models/Qwen3.5/Qwen3.5-9B
LOG=v2a_p2_queue.log
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

LOCK=/tmp/v2a_p2_queue.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "[queue] another instance holds the lock; exiting" >> $LOG; exit 1
fi
trap 'rmdir "$LOCK"' EXIT

echo "[queue] $(date) waiting for route2 pid $PID_TO_WAIT" >> $LOG
while kill -0 "$PID_TO_WAIT" 2>/dev/null; do sleep 60; done
echo "[queue] $(date) route2 gone; waiting for GPU < 4 GiB" >> $LOG
while [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)" -gt 4000 ]; do
  sleep 60
done
sleep 30   # allocator settle

echo "[queue] $(date) GATE C start (8-row constrained smoke)" >> $LOG
$PY v2a_eval.py --model $M --adapter v2a_a/adapter_v1 --data v2a_A_dev.jsonl \
    --out-dir v2a_a --tag smoke_p2 --limit 8 --max-new-tokens 512 --constrained >> $LOG 2>&1
rc=$?
echo "[queue] $(date) gate C exit=$rc" >> $LOG
if [ $rc -ne 0 ]; then echo "[queue] GATE C FAILED (crash) - STOP, no gate D" >> $LOG; exit 1; fi

PASS=$($PY - << 'EOF'
import json
# C-revised criteria (owner-approved protocol revision 2026-09-18):
# grammar correctness + runtime only; truncation is diagnostic, not a gate.
m = json.load(open('v2a_a/v2a_smoke_p2_eval_metrics.json'))
preds = [json.loads(l) for l in open('v2a_a/v2a_smoke_p2_predictions.jsonl', encoding='utf-8')]
maxnew = m['decoding']['max_new_tokens']
malformed_nontrunc = sum(1 for p in preds
                         if not p.get('ok') and p.get('n_gen_tokens', 0) < maxnew)
checks = {
    'malformed_nontruncated_zero': malformed_nontrunc == 0,
    'invalid_operator_zero': m['out_of_catalog_operator_instances'] == 0,
    'runtime_speed': m.get('gen_tok_per_sec_median', 0) > 5,
    'runtime_mem': m.get('gpu_peak_gb', 99) < 20,
}
failed = [k for k, v in checks.items() if not v]
print('PASS' if not failed else 'FAIL:' + ','.join(failed))
EOF
)
echo "[queue] $(date) gate C criteria: $PASS" >> $LOG
if [ "$PASS" != "PASS" ]; then echo "[queue] GATE C FAILED (criteria) - STOP" >> $LOG; exit 1; fi

echo "[queue] $(date) GATE D start" >> $LOG
bash run_v2a_p2_eval.sh >> $LOG 2>&1
echo "[queue] $(date) ALL DONE (gate D chain finished)" >> $LOG
