# -*- coding: utf-8 -*-
"""
Rebuild outputs_v2 step7 from the latest v2 step6 and graft task_metadata.

The old step7 ran with a more complete facts_summary CSV set (~115k matches
for ~132 task types).  The local rebuild only has a partial facts_summary set
available, so we reuse the script_id -> task_metadata map from the old step7
output and apply it to the latest v2 step6 workflows.
"""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
OLD_V4 = ROOT / "outputs" / "pipeline" / "step7" / "labeled_workflows_l3_v4.json"
V2_STEP6 = ROOT / "outputs_v2" / "pipeline" / "step6" / "labeled_workflows_l3.json"
V2_V4 = ROOT / "outputs_v2" / "pipeline" / "step7" / "labeled_workflows_l3_v4.json"
V2_VOCAB = ROOT / "outputs_v2" / "pipeline" / "step7" / "task_type_vocabulary_v4.json"
MIN_CONTENT_LENGTH = 3


def content_length(workflow: dict) -> int:
    return sum(1 for token in workflow.get("l3_sequence", []) if isinstance(token, int) and token >= 0)


def main():
    print(f"Loading old step7 task_metadata map: {OLD_V4}")
    with OLD_V4.open(encoding="utf-8") as f:
        old = json.load(f)
    old_map: dict[str, dict] = {}
    for wf in old["labeled_workflows"]:
        sid = wf["metadata"]["script_id"]
        tm = wf.get("task_metadata", {})
        if tm.get("task_type") and tm["task_type"] != "Unknown":
            old_map[sid] = tm
    print(f"  old script_id with task_type: {len(old_map):,}")

    print(f"Loading latest v2 step6: {V2_STEP6}")
    with V2_STEP6.open(encoding="utf-8") as f:
        v2 = json.load(f)
    source_wfs = v2["labeled_workflows"]

    matched = unmatched = filtered_short = 0
    wfs = []
    for wf in source_wfs:
        if content_length(wf) < MIN_CONTENT_LENGTH:
            filtered_short += 1
            continue
        sid = wf["metadata"]["script_id"]
        if sid in old_map:
            wf["task_metadata"] = old_map[sid]
            matched += 1
        else:
            wf["task_metadata"] = {"task_type": "Unknown", "task_name": "", "task_description": ""}
            unmatched += 1
        wfs.append(wf)
    print(f"  v2 source: {len(source_wfs):,}")
    print(f"  filtered short (<{MIN_CONTENT_LENGTH} content tokens): {filtered_short:,}")
    print(f"  v2 grafted: {matched:,}  unmatched (set 'Unknown'): {unmatched:,}")

    # Rebuild task_type_vocabulary
    tt_counter = Counter(w["task_metadata"]["task_type"] for w in wfs)
    print(f"  task_types: {len(tt_counter)}")
    for t, n in tt_counter.most_common(15):
        print(f"    {t[:40]:<40}  {n:,}")

    task_types = sorted(set(
        w["task_metadata"]["task_type"] for w in wfs
        if w["task_metadata"]["task_type"] != "Unknown"
    ))
    task_type_to_id = {"Unknown": 0}
    id_to_task_type = {0: "Unknown"}
    for i, t in enumerate(task_types, start=1):
        task_type_to_id[t] = i
        id_to_task_type[i] = t

    with V2_V4.open("w", encoding="utf-8") as f:
        json.dump({
            "num_workflows": len(wfs),
            "labeled_workflows": wfs,
            "statistics": {
                "total": len(source_wfs),
                "filtered_short": filtered_short,
                "kept": len(wfs),
                "matched": matched,
                "unmatched": unmatched,
                "metadata_source": str(OLD_V4.relative_to(ROOT)),
            },
        }, f, ensure_ascii=False)
    with V2_VOCAB.open("w", encoding="utf-8") as f:
        json.dump({
            "task_type_to_id": task_type_to_id,
            "id_to_task_type": {str(k): v for k, v in id_to_task_type.items()},
            "num_types": len(task_type_to_id),
        }, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {V2_V4}")
    print(f"  Wrote {V2_VOCAB}  ({len(task_type_to_id)} types)")


if __name__ == "__main__":
    main()
