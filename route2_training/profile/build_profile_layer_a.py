"""Build QGIS Operator Capability Profile - Layer A (identity + types).

Deterministic, from the SHA-pinned benchmark catalog (1,291 operators,
benchmarks/qgis_planner_v1/authority/qgis_catalog.json).

Layer B (parameter schema: slots/required/optional/descriptions) pends
Neo4j (QGIS_Operator hasInput/hasOutput -> Input nodes with
parameter_name/description/optional). Layer C (operation_intent) pends
LLM enrichment + sampled audit. Both attach to the same profile file
with coverage fields; layer_a=True marks this build's completeness.
"""

import hashlib
import json
from pathlib import Path

CATALOG = Path('benchmarks/qgis_planner_v1/authority/qgis_catalog.json')
OUT = Path('route2_training/profile/qgis_operator_capability_profile_v0_1.json')

TYPE_NORM = {'polygon': 'vector', 'point': 'vector', 'line': 'vector', 'table': 'vector',
             'features': 'vector', 'vector': 'vector', 'raster': 'raster', 'grid': 'raster',
             'dem': 'raster'}


def norm_types(ts):
    out = set()
    for t in ts or []:
        t = t.strip().lower()
        if t == 'literaldata':
            continue
        out.add(TYPE_NORM.get(t, t))
    return sorted(out)


def main() -> None:
    cat = json.loads(CATALOG.read_text(encoding='utf-8'))
    profile = {}
    for op in cat['operators']:
        oid = op['operator_id']
        profile[oid] = {
            'operator_id': oid,
            'official_name': op['official_name'],
            'provider': op['provider'],
            'input_types_raw': op.get('input_types', []),
            'output_types_raw': op.get('output_types', []),
            'input_types_norm': norm_types(op.get('input_types')),
            'output_types_norm': norm_types(op.get('output_types')),
            'layer_a': True,
            'layer_b_params': None,
            'layer_c_intent': None,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(profile, ensure_ascii=False, indent=1, sort_keys=True).encode('utf-8')
    OUT.write_bytes(blob)
    multi_in = sum(1 for v in profile.values() if len(v['input_types_norm']) >= 2)
    print(f"Profile v0.1: {len(profile)} operators -> {OUT}")
    print(f"  multi-input (normalized>=2 types): {multi_in}")
    print(f"  sha256: {hashlib.sha256(blob).hexdigest()[:16]}")
    from collections import Counter
    sig = Counter((tuple(v['input_types_norm']), tuple(v['output_types_norm']))
                  for v in profile.values())
    print("  top-3 I/O signatures:", sig.most_common(3))


if __name__ == '__main__':
    main()
