#!/bin/bash
# M1-R2 Phase 2-D SFT launch — protocol identical to run_m1_r1.sh, only the
# decoder backbone init comes from the DAPT carry set (via m1_r2_sft.py).
set -u
cd /home/qy/system_redesign
export GIS_VOCAB_PROFILE=paper_v1_128
export GIS_V4_TRAINER=platform_r1
export HF_HUB_OFFLINE=1
LOG=/home/qy/gee_llm_smoke/m1_r2_sft_training.log
echo "=== M1-R2 SFT LAUNCH $(date) ===" >> $LOG
echo "carry=0bd32ca2ad8af8a65d017767569f74b078fcbe6123af4e8f7a10bef1d210fdf3 dapt=83d5674587d7b582aee51050785cfe5729fee0374df71b5f9a585b7133059173" >> $LOG
/home/qy/miniconda3/envs/transformer/bin/python scripts/m1_r2_sft.py >> $LOG 2>&1
echo "=== M1-R2 SFT EXIT=$? $(date) ===" >> $LOG
