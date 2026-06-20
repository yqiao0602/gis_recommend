#!/usr/bin/env python3
"""Check 3k batch progress on server."""
import paramiko, os

PW = os.environ.get("SERVER_PW", "")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.191.2.38", username="qy", password=PW, timeout=15)

# Sample count
sin, sout, _ = ssh.exec_command("wc -l /home/qy/system_redesign/outputs_v2/api_l3_samples_3k.jsonl 2>/dev/null || echo 0")
samples = int(sout.read().decode().strip().split()[0])

# Checkpoint
sin, sout, _ = ssh.exec_command("cat /home/qy/system_redesign/outputs_v2/api_l3_checkpoint_3k.json")
import json
try:
    ck = json.loads(sout.read().decode())
    p = len(ck.get("processed", []))
    k = ck.get("kept", 0)
    t = ck.get("total_attempts", 0)
    last = ck.get("script_last", "?")
except:
    p = k = t = 0
    last = "?"

# Process alive
sin, sout, _ = ssh.exec_command("ps aux | grep server_batch | grep python | grep -v grep | wc -l")
alive = int(sout.read().decode().strip())

yield_rate = f"{k}/{t}={100*k/max(t,1):.0f}%" if t else "N/A"
print(f"Samples: {samples}  |  Checkpoint: processed={p} kept={k} attempts={t}  |  Yield: {yield_rate}  |  Alive: {alive}  |  Last: {last}")

ssh.close()
