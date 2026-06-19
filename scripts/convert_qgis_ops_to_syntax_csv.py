#!/usr/bin/env python3
"""Convert yll's qgis_operators.json to the Operator Syntax KB CSV format
expected by his workflow abstraction postprocessor pipeline.

Output columns: full_name, short_name, description, output_type, parameters
"""
import json, csv, sys
from pathlib import Path

def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else "/home/qy/system_redesign/pipeline_study/qgis_operators.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "/home/qy/system_redesign/pipeline_study/qgis_operator_syntax_kb.csv"
    ops = json.loads(Path(inp).read_text(encoding="utf-8"))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["full_name", "short_name", "description", "output_type", "parameters"])
        for op in ops:
            name = op.get("name", "")
            ident = op.get("identifier", "")
            desc = (op.get("description") or "")[:200]
            outs = op.get("outputs", [])
            out_type = outs[0].get("type", "") if outs else ""
            ins = op.get("inputs", [])
            params = "; ".join(f"{p.get('name','')}:{p.get('type','')}" for p in ins[:6])
            w.writerow([ident or name, name, desc, out_type, params])
    print(f"converted {len(ops)} QGIS operators -> {out}")

if __name__ == "__main__":
    main()
