#!/usr/bin/env bash
# P0-B2 completion gate: wait for arm C predictions, then run three-arm report.
while pgrep -f 'p0b2_[a]rms' >/dev/null; do sleep 120; done
test -s /home/qy/p0b2_arm_C/predictions.json || { echo "ARM_C_EXITED_WITHOUT_SAVING"; exit 1; }
cd /home/qy/system_redesign
/home/qy/miniconda3/envs/qwen35/bin/python /home/qy/p0b2_three_arm_report.py
echo "THREE_ARM_REPORT_DONE"
