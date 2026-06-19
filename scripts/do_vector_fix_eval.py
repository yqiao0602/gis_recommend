#!/usr/bin/env python3
"Thin driver: V4.6-vecfix showcase on 80 tasks -> harness score -> 3-way compare"
import subprocess, sys, json, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gis_recommend.evaluation.qgis_operator_registry import load_algid_io_types
from gis_recommend.evaluation.open_landing_report import parse_showcase_csv, build_report, compare_reports, render_comparison_markdown

env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
DIAG = ROOT / "outputs_v2" / "diagnostics"
OUT = DIAG / "open_landing_vector_fix"
OUT.mkdir(parents=True, exist_ok=True)

# 1. showcase (vector-fix checkpoint, 80 tasks)
print("[1/3] Running V4.6-vecfix showcase (80 tasks)...")
subprocess.run([
    sys.executable, str(ROOT / "scripts" / "run_end_to_end_showcase_eval.py"),
    "--task-file", str(DIAG / "open_landing_v46" / "open_landing_tasks.jsonl"),
    "--output-dir", str(OUT / "showcase_vf"),
    "--checkpoint", str(ROOT / "outputs_v2" / "transformer_checkpoints_v4_6_vector_fix" / "best_model.pth"),
    "--max-tasks", "80",
], check=True, env=env)

# 2. score
print("[2/3] Scoring...")
io = load_algid_io_types()
items_vf = parse_showcase_csv(OUT / "showcase_vf" / "end_to_end_showcase_eval.csv")
vf_report = build_report(items_vf, io)
(OUT / "v46_vector_fix_report.json").write_text(json.dumps(vf_report, ensure_ascii=False, indent=2))
(OUT / "v46_vector_fix_report.md").write_text(render_markdown(vf_report))

# 3. compare vs baseline and V4.6
base = json.loads((DIAG / "open_landing_eval" / "open_landing_report.json").read_text(encoding="utf-8"))
v46 = build_report(parse_showcase_csv(DIAG / "open_landing_v46" / "end_to_end_showcase_eval.csv"), io)

print("\n=== BASELINE vs V4.6 vs V4.6-VECFIX ===")
for m in ["vec", "rast", "mixed"]:
    b = base["by_modality"].get(m, {})
    v = v46["by_modality"].get(m, {})
    f = vf_report["by_modality"].get(m, {})
    print(f"  {m:6s}: exec={b.get('executable_rate','?'):.2f}->{v.get('executable_rate','?'):.2f}->{f.get('executable_rate','?'):.2f}  "
          f"unique={b.get('unique_ratio','?'):.2f}->{v.get('unique_ratio','?'):.2f}->{f.get('unique_ratio','?'):.2f}  "
          f"valid={(v.get('operator_validity')or'-')}->{f.get('operator_validity','?')}",
          end="")
    dv = (v.get("executable_rate") or 0) - b.get("executable_rate", 0)
    df = (f.get("executable_rate") or 0) - (v.get("executable_rate") or 0)
    print(f"  V4.6Δ={dv:+.2f} vecfixΔ={df:+.2f}")

# two-way compare: V4.6 vs vecfix
cmp = compare_reports(v46, vf_report, labels=("v4.6", "v4.6-vecfix"))
(OUT / "v46_vs_vecfix.json").write_text(json.dumps(cmp, ensure_ascii=False, indent=2))
(OUT / "v46_vs_vecfix.md").write_text(render_comparison_markdown(cmp))
print("\n[3/3] Done ->", OUT)
