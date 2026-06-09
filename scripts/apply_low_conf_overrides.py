#!/usr/bin/env python3
"""
Apply manual overrides for 30 low-confidence QGIS mappings from REVIEW_61 analysis.

Decision categories:
- REMOVE: Delete mapping (no reasonable L3 target)
- SKIP: Add to skip list (getter/metadata access)
- ADOPT_T2/T3: Use LLM's 2nd/3rd choice instead of top-1
- KEEP: Keep current mapping (suboptimal but acceptable)
"""

import json
from pathlib import Path

# Manual override decisions based on analysis
OVERRIDES = {
    # === REMOVE (14 ops) - No reasonable L3 target ===
    "Rasterize": {"action": "REMOVE", "reason": "Generic conversion, no specific L3"},
    "Extract binary field": {"action": "REMOVE", "reason": "Getter, not transformation"},
    "Extract Shapefile encoding": {"action": "REMOVE", "reason": "Metadata getter"},
    "v.in.dxf": {"action": "REMOVE", "reason": "Format import, no L3 target"},
    "r.fillnulls": {"action": "REMOVE", "reason": "Ambiguous interpolation method"},
    "r.sun.insoltime": {"action": "REMOVE", "reason": "Niche solar calculation"},
    "Raster surface volume": {"action": "REMOVE", "reason": "Niche volume calculation"},
    "GeneratePlyFile": {"action": "REMOVE", "reason": "Format export"},
    "ReadImageInfo": {"action": "REMOVE", "reason": "Metadata getter"},
    "Least Cost Paths": {"action": "REMOVE", "reason": "Complex routing, no L3 target"},
    "Natural Neighbour": {"action": "REMOVE", "reason": "Specific interpolation method"},
    "Sunrise and Sunset": {"action": "REMOVE", "reason": "Niche solar calculation"},
    "Build overviews": {"action": "REMOVE", "reason": "Optimization, not transformation"},
    "r.ros": {"action": "REMOVE", "reason": "Niche fire spread model"},

    # === SKIP (3 ops) - Add to skip list ===
    "Filter layers by type": {"action": "SKIP", "reason": "Metadata filter"},
    "Export to PostgreSQL database available connections": {"action": "SKIP", "reason": "Export operation"},
    "Export to PostgreSQL database new connection": {"action": "SKIP", "reason": "Export operation"},

    # === ADOPT_T2/T3 (6 ops) - Use LLM alternative ===
    "Remove Duplicate Points": {"action": "ADOPT_T2", "new_l3": "L3_02_06_01", "reason": "T2 'Remove Duplicates' 0.25 > T1 'Logical Comparison' 0.30"},
    "PCT to RGB": {"action": "ADOPT_T2", "new_l3": "L3_03_01_04", "reason": "T2 'Color Manipulation' 0.25 > T1 'Arithmetic Math' 0.30"},
    "Sieve": {"action": "ADOPT_T2", "new_l3": "L3_03_04_01", "reason": "T2 'Reclassify / Remap' 0.85 > invalid legacy logical-op code"},
    "r.fill.dir": {"action": "ADOPT_T2", "new_l3": "L3_04_01_01", "reason": "T2 'Flow Direction' 0.25 > T1 'Slope Gradient' 0.30"},
    "Kernel Density Estimation": {"action": "ADOPT_T2", "new_l3": "L3_03_02_03", "reason": "T2 'Density Analysis' 0.25 > T1 'Interpolation' 0.30"},
    "Mirror Raster": {"action": "ADOPT_T3", "new_l3": "L3_03_09_05", "reason": "T3 'Geometric Transform' 0.15 > T1 'Arithmetic Math' 0.20"},

    # === KEEP (7 ops) - Suboptimal but acceptable ===
    "Polygon Categories to Raster": {"action": "KEEP", "reason": "Current 'Temporal Reducer' wrong but no clear alternative"},
    "Proximity Raster": {"action": "KEEP", "reason": "Current 'Arithmetic Math' suboptimal but usable"},
    "Transpose Rasters": {"action": "KEEP", "reason": "Current 'Arithmetic Math' suboptimal but usable"},
    "r.out.ascii": {"action": "KEEP", "reason": "Export op, current 'Data Type Conversion' acceptable"},
    "v.edit": {"action": "KEEP", "reason": "Generic edit, current 'Data Import' acceptable"},
    "Write Vector Tiles_mbtiles": {"action": "KEEP", "reason": "Export op, current 'Data Import' acceptable"},
    "Write Vector Tiles_xyz": {"action": "KEEP", "reason": "Export op, current 'Data Import' acceptable"},
}

def main():
    base_dir = Path(__file__).parent.parent
    id_mappings_path = base_dir / "outputs_v2" / "id_mappings_v2.json"
    skip_list_path = base_dir / "outputs_v2" / "qgis_skip_list_v2.json"

    # Load current mappings
    with open(id_mappings_path, encoding='utf-8') as f:
        id_mappings = json.load(f)

    qgis_mapping = id_mappings.get('mapping_metadata', {}).get('qgis_to_l3', {})

    # Load or create skip list
    if skip_list_path.exists():
        with open(skip_list_path, encoding='utf-8') as f:
            skip_list = json.load(f)
    else:
        skip_list = {"skip_operators": [], "reason": "QGIS operators to skip"}

    # Apply overrides
    stats = {"REMOVE": 0, "SKIP": 0, "ADOPT_T2": 0, "ADOPT_T3": 0, "KEEP": 0, "NOT_FOUND": 0}

    for op_name, decision in OVERRIDES.items():
        action = decision["action"]

        if op_name not in qgis_mapping:
            stats["NOT_FOUND"] += 1
            print(f"[NOT_FOUND] {op_name} - already removed or never existed")
            continue

        if action == "REMOVE":
            del qgis_mapping[op_name]
            stats["REMOVE"] += 1
            print(f"[REMOVE] {op_name} - {decision['reason']}")

        elif action == "SKIP":
            del qgis_mapping[op_name]
            skip_list["skip_operators"].append({
                "operator": op_name,
                "reason": decision["reason"]
            })
            stats["SKIP"] += 1
            print(f"[SKIP] {op_name} - {decision['reason']}")

        elif action in ["ADOPT_T2", "ADOPT_T3"]:
            old_l3 = qgis_mapping[op_name]["primary_l3"]
            new_l3 = decision["new_l3"]
            qgis_mapping[op_name]["primary_l3"] = new_l3
            qgis_mapping[op_name]["mapping_confidence"] = "manual_override"
            qgis_mapping[op_name]["override_reason"] = decision["reason"]
            stats[action] += 1
            print(f"[{action}] {op_name}: {old_l3} → {new_l3} - {decision['reason']}")

        elif action == "KEEP":
            qgis_mapping[op_name]["mapping_confidence"] = "manual_reviewed"
            qgis_mapping[op_name]["review_note"] = decision["reason"]
            stats["KEEP"] += 1
            print(f"[KEEP] {op_name} - {decision['reason']}")

    # Save updated mappings
    id_mappings['mapping_metadata']['qgis_to_l3'] = qgis_mapping
    with open(id_mappings_path, 'w', encoding='utf-8') as f:
        json.dump(id_mappings, f, indent=2, ensure_ascii=False)

    # Save updated skip list
    with open(skip_list_path, 'w', encoding='utf-8') as f:
        json.dump(skip_list, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "="*60)
    print("Override Summary:")
    for action, count in stats.items():
        print(f"  {action}: {count}")
    print(f"\nTotal QGIS mappings: {len(qgis_mapping)}")
    print(f"Total QGIS skip list: {len(skip_list['skip_operators'])}")
    print(f"\nUpdated: {id_mappings_path}")
    print(f"Updated: {skip_list_path}")

if __name__ == "__main__":
    main()
