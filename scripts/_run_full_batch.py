#!/usr/bin/env python3
"""Launch full-scale 68k batch on server."""
import paramiko, os, time

PW = os.environ.get("SERVER_PW", "")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not PW or not API_KEY:
    print("ERROR: set SERVER_PW and DEEPSEEK_API_KEY"); exit(1)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.191.2.38", username="qy", password=PW, timeout=15)
print("Connected")

# Push latest script
sftp = ssh.open_sftp()
sftp.put("scripts/server_batch_api_to_l3.py", "/home/qy/system_redesign/scripts/server_batch_api_to_l3.py")
sftp.close()
print("Script pushed")

# Kill old
ssh.exec_command("pkill -f server_batch_api_to_l3 2>/dev/null || true", timeout=5)
time.sleep(1)

# Start full batch — no max-scripts limit (process all 68k)
cmd = (
    'cd /home/qy/system_redesign && '
    'export DEEPSEEK_API_KEY="' + API_KEY + '" && '
    'source ~/miniconda3/etc/profile.d/conda.sh && '
    'conda activate transformer && '
    'nohup python scripts/server_batch_api_to_l3.py '
    '--max-scripts 0 --batch-size 500 --sleep 0.3 '
    '--out outputs_v2/api_l3_samples_full.jsonl '
    '--checkpoint outputs_v2/api_l3_checkpoint_full.json '
    '> outputs_v2/api_l3_batch_full.log 2>&1 &'
)
print(f"Launching full batch (all 68k scripts)...")
ssh.exec_command(cmd, timeout=10)
time.sleep(3)

# Verify
for check in [
    "ps aux | grep server_batch | grep python | grep -v grep | wc -l",
    "wc -l /home/qy/system_redesign/outputs_v2/api_l3_samples_full.jsonl 2>/dev/null || echo 0",
]:
    sin, sout, _ = ssh.exec_command(check, timeout=5)
    print(f"  {sout.read().decode().strip()}")

ssh.close()
print("\nFull batch started.")
print(f"Estimated: 68k scripts × 40% yield = ~27,000 samples")
print(f"Estimated runtime: ~5-6 hours @ 0.3s sleep per call")
