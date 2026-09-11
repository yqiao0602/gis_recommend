"""Find the malformed line in the draft JSONL."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
p = WT / "benchmarks" / "qgis_planner_v1" / "authority" / "v02_task_derivation_draft_v1.jsonl"
for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
    if not line.strip():
        continue
    try:
        json.loads(line)
    except json.JSONDecodeError as ex:
        print(f"line {i+1} BAD: {ex}")
        print(" ", line[:200])
        print("  ...", line[max(0, ex.pos - 60):ex.pos + 60])
