"""Fix the draft JSONL: compact the multi-line header into one line."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
p = WT / "benchmarks" / "qgis_planner_v1" / "authority" / "v02_task_derivation_draft_v1.jsonl"
lines = p.read_text(encoding="utf-8").splitlines()

# find the end of the multi-line header (first line that is exactly '}')
header_end = next(i for i, l in enumerate(lines) if l.strip() == "}")
header = json.loads("\n".join(lines[: header_end + 1]))
rest = [l for l in lines[header_end + 1:] if l.strip()]
print("header keys:", len(header), "| record lines:", len(rest))
for i, l in enumerate(rest):
    json.loads(l)  # must all parse

with p.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for l in rest:
        f.write(l + "\n")
print("fixed:", p.name)
