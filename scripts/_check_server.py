#!/usr/bin/env python3
"""Check server batch progress."""
import paramiko, os

PW = os.environ.get("SERVER_PW", "")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.191.2.38", username="qy", password=PW, timeout=15)

# Check samples count and checkpoint
for cmd in [
    "wc -l /home/qy/system_redesign/outputs_v2/api_l3_samples_2k.jsonl",
    "python3 -c \"import json; c=json.load(open('/home/qy/system_redesign/outputs_v2/api_l3_checkpoint_2k.json')); print(len(c['processed']), c.get('kept',0), c.get('total_attempts',0), c.get('script_last','?'))\"",
    "ps aux | grep server_batch | grep python | grep -v grep | wc -l",
]:
    sin, sout, serr = ssh.exec_command(cmd, timeout=10)
    out = sout.read().decode().strip()
    err = serr.read().decode().strip()
    print(f"> {cmd[:60]}...")
    if out:
        print(f"  {out[:400]}")
    if err and "ERROR" not in err:
        pass

ssh.close()
