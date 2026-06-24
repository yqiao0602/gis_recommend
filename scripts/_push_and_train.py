#!/usr/bin/env python3
"""⚠️ DEPRECATED 2026-06-24 — 已被审查标记为高优先级问题。

问题：
  1. --workflows/--epochs 与 train_v4_6_quality_gate.py 的 --data/--num-epochs 不匹配。
  2. 自动 pkill -f train_v4_6 可能误杀其他训练进程。
  3. 上传的是 vector_v2 数据，但脚本名叫 unified，造成实验记录混乱。

正确做法：
  直接在服务器上运行 train_v4_6_quality_gate.py，显式传:
    --data outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/...
    --splits outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/...
    --task-vocab outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/...
    --length-stats outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/...
    --warmstart <dpo_v2_48task_ckpt>
    --num-epochs 5

本文件保留仅供参考，不可直接用于训练。

（审查意见见 2026-06-24 用户代码审查。）
"""
import sys


if "--force-deprecated" not in sys.argv:
    raise SystemExit(
        "scripts/_push_and_train.py 已弃用，默认不会执行 SSH/SFTP/远程训练。\n"
        "请直接在服务器运行 scripts/train_v4_6_quality_gate.py，并显式传入 "
        "--data/--splits/--task-vocab/--length-stats/--warmstart/--num-epochs。\n"
        "如果只是为了复现旧行为，必须显式加 --force-deprecated。"
    )

sys.argv.remove("--force-deprecated")

import os
import time

import paramiko

PW = os.environ.get("SERVER_PW", "")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.191.2.38", username="qy", password=PW, timeout=30)

# Step 1: Push training data
print("Pushing data files (210MB total, may take 2-3 min)...")
sftp = ssh.open_sftp()
sftp.put(
    "outputs_v2/labeled_workflows_l3_v4_vector_v2.json",
    "/home/qy/system_redesign/outputs_v2/labeled_workflows_l3_v4_vector_v2.json",
)
sftp.put(
    "outputs_v2/dataset_splits_v4_vector_v2.json",
    "/home/qy/system_redesign/outputs_v2/dataset_splits_v4_vector_v2.json",
)
sftp.close()
print("Data pushed")

# Step 2: Check if training script exists on server
sin, sout, serr = ssh.exec_command(
    "ls /home/qy/system_redesign/scripts/train_v4_6_quality_gate.py 2>/dev/null && echo EXISTS || echo MISSING",
    timeout=10
)
has_script = "EXISTS" in sout.read().decode()
print(f"Training script: {'EXISTS' if has_script else 'MISSING'}")

if not has_script:
    sftp = ssh.open_sftp()
    sftp.put(
        "scripts/train_v4_6_quality_gate.py",
        "/home/qy/system_redesign/scripts/train_v4_6_quality_gate.py",
    )
    print("Training script pushed")
    sftp.close()

# Step 3: Check if there's an old training running — 不再自动 pkill
sin, sout, serr = ssh.exec_command(
    "ps aux | grep train_v4_6 | grep -v grep | wc -l", timeout=10
)
running = sout.read().decode().strip()
if running != "0":
    print(f"WARN: {running} training processes already running.")
    print("  ⚠️  不再自动 pkill（审查要求：避免误杀其他训练）。")
    print("  请手动停止后重试。")
    ssh.close()
    exit(1)

# Step 4: Launch training — ⚠️ 参数已修正为 train_v4_6_quality_gate.py 格式
train_cmd = (
    "cd /home/qy/system_redesign && "
    "source ~/miniconda3/etc/profile.d/conda.sh && "
    "conda activate transformer && "
    "nohup python scripts/train_v4_6_quality_gate.py "
    "--data outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/labeled_workflows_l3_v4_quality_gate_qgis_vector_oversampled.json "
    "--splits outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/dataset_splits_v4_quality_gate_qgis_vector_oversampled.json "
    "--task-vocab outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_vocabulary_v4_quality_gate_qgis_vector_oversampled.json "
    "--num-epochs 50 "
    "--length-stats outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_length_stats.json "
    "> outputs_v2/train_v46_phase10.log 2>&1 &"
)
print(f"Launching: {train_cmd[:120]}...")
sin, sout, serr = ssh.exec_command(train_cmd, timeout=10)
time.sleep(5)

sin, sout, serr = ssh.exec_command(
    "ps aux | grep train_v4_6 | grep -v grep | wc -l; "
    "echo ---; "
    "tail -3 /home/qy/system_redesign/outputs_v2/train_v46_phase10.log 2>/dev/null || echo 'no log yet'",
    timeout=10
)
print(sout.read().decode())

ssh.close()
print("\n⚠️  此脚本已弃用。建议直接在服务器上运行训练命令。")
