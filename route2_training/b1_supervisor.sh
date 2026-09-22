#!/bin/bash
# Route-2 B1 supervisor: (re)launch training if not running, then watch for
# exit -> DONE.flag. Idempotent (pgrep guard), safe to call repeatedly.
#
# Autoboot path: cron @reboot calls this ~60s after boot. Gated by the
# AUTOBOOT.enabled marker — remove that file when the B1 line is finished
# to make this a permanent no-op without touching crontab again.
MARKER=/home/qy/gee_llm_smoke/route2_B1/AUTOBOOT.enabled
FLAG=/home/qy/gee_llm_smoke/route2_B1/DONE.flag
[ -f "$MARKER" ] || exit 0
pgrep -f B1_gee >/dev/null && exit 0
rm -f "$FLAG"
cd /home/qy/system_redesign || exit 1
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  nohup /home/qy/miniconda3/envs/qwen35/bin/python route2_training/train.py \
  --config route2_training/configs/B1_gee_semantic_qgis_sft.yaml --release \
  >> /home/qy/gee_llm_smoke/route2_B1/release.log 2>&1 &
sleep 2
nohup bash -c "while pgrep -f B1_gee >/dev/null; do sleep 300; done; sleep 60; touch $FLAG" \
  >/dev/null 2>&1 &
echo "B1 supervisor: launched pid $(pgrep -f B1_gee | head -1), flag watcher armed"
