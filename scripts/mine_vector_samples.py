#!/usr/bin/env python3
"""
Targeted vector sample mining from .py scripts.

1. Find .py scripts with vector QGIS operations
2. Extract operator sequences via processing.runalg()
3. Map each operator to L3 code via semantic scores
4. Quality gate, dedup, save as training samples
"""

import json, os, re, sys, time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEE = '/home/yll/GEE'
OUTPUT_DIR = ROOT / 'outputs_v2' / 'targeted_vector_mining_v2'
SEMANTIC_SCORES = ROOT / 'outputs' / 'l3_qgis_semantic_scores.json'

# Manual patches for operators that semantic mapping missed
OP_PATCH = {
    'joinattributesbylocation': 'L3_02_04_01',     # Spatial Join
    'joinbylocation': 'L3_02_04_01',
    'selectbylocation': 'L3_02_06_03',             # Extract by Location
    'extractbylocation': 'L3_02_06_03',
    'boundingboxes': 'L3_02_05_12',                # Min Bounding Geometry
    'minimumboundinggeometry': 'L3_02_05_12',
    'orientedminimumboundingbox': 'L3_02_05_12',
    'selectbyattribute': 'L3_02_06_01',            # Select by Attribute
    'selectbyexpression': 'L3_02_06_01',
    'filterbygeometry': 'L3_02_06_05',             # Filter by Geometry
    'filterverticesbym': 'L3_02_06_05',
}

# ── Load QGIS → L3 mapping ───────────────────────────────────────

def _normalize(s: str) -> str:
    """Normalize names for matching: remove spaces, underscores, special chars."""
    return re.sub(r'[\s_\-\.]', '', s.lower())

def load_qgis_to_l3(semantic_path: Path) -> dict[str, str]:
    """Build QGIS operator name → best L3 code mapping from semantic scores."""
    if not semantic_path.exists():
        return {}
    raw = json.load(open(semantic_path, 'r', encoding='utf-8'))
    mapping = {}
    for section in ['scores', 'discovered_mappings']:
        section_data = raw.get(section, {})
        if not isinstance(section_data, dict):
            continue
        for l3_code, entries in section_data.items():
            if not l3_code.startswith('L3_02'):
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                qname = entry.get('qgis_name', '')
                score = entry.get('semantic_score', 0)
                if not qname or score < 0.3:
                    continue
                key = _normalize(qname)  # normalized key
                old = mapping.get(key)
                if old is None:
                    mapping[key] = (l3_code, score)
                elif old[1] < score:
                    mapping[key] = (l3_code, score)
    return mapping


def map_op_to_l3(alg_id: str, mapping: dict[str, tuple]) -> str | None:
    """Map a QGIS alg_id to its best L3 code."""
    if not mapping:
        return None
    op_name = _normalize(alg_id.split(':')[-1])  # normalize alg_id part
    # Check patch table first (manual corrections)
    if op_name in OP_PATCH:
        return OP_PATCH[op_name]
    # Check semantic mapping
    if op_name in mapping:
        return mapping[op_name][0]
    # Try partial match
    for qname, (l3_code, score) in mapping.items():
        if qname in op_name or op_name in qname:
            return l3_code
    return None


# ── .py script mining ────────────────────────────────────────────

VEC_KEYWORDS = [
    'buffer', 'clip', 'intersect', 'difference', 'dissolve', 'merge',
    'centroid', 'extractby', 'selectby', 'split', 'joinattributes',
    'union', 'singlesided', 'variable', 'multipart', 'bounding',
    'fieldcalculator', 'deletecolumn', 'reprojectlayer', 'simplify',
    'fixgeometries', 'concavehull', 'delaunay', 'voronoipolygons',
    'countpointsinpolygon', 'distancetonearest', 'snap',
    'polygonstolines', 'linestopolygons', 'saveselectedfeatures',
    'deletefeatures', 'addfield', 'refactorfields', 'deleteholes',
    'convertgeometrytype', 'translatex', 'smooth', 'grid',
]


def find_all_vector_py_scripts() -> list[str]:
    """Find ALL .py files with vector QGIS operations."""
    found = []
    for root, dirs, files in os.walk(GEE):
        if 'QGIS' not in root:
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, 'r', encoding='utf-8-sig', errors='ignore') as fh:
                    content = fh.read(16384)
                has_run = 'processing.run' in content
                has_vec = any(kw in content.lower() for kw in VEC_KEYWORDS)
                if has_run and has_vec:
                    found.append(fp)
            except:
                continue
            if len(found) % 5000 == 0:
                print(f'  Found {len(found)} vector scripts...')
    return found


def extract_ops_from_py(fpath: str) -> list[str]:
    """Extract QGIS alg_ids from a .py script."""
    with open(fpath, 'r', encoding='utf-8-sig', errors='ignore') as f:
        content = f.read()
    alg_ids = []
    seen = set()
    for m in re.finditer(r'''processing\.(?:runalg|run)\s*\(\s*['"]([^'"]+)['"]''', content):
        aid = m.group(1)
        if aid not in seen:
            seen.add(aid)
            alg_ids.append(aid)
    return alg_ids


def main():
    api_key = os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('LLM_API_KEY')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load mapping
    print('[1] Loading QGIS → L3 semantic mapping...')
    qgis_to_l3 = load_qgis_to_l3(SEMANTIC_SCORES)
    print(f'  {len(qgis_to_l3)} QGIS operators mapped to vector L3 codes')
    for qname, (l3, score) in sorted(qgis_to_l3.items())[:10]:
        print(f'    {qname:30s} → {l3} (score={score:.2f})')

    # 2. Find vector scripts
    print(f'\n[2] Finding ALL vector .py scripts...')
    scripts = find_all_vector_py_scripts()
    print(f'  Found {len(scripts)} scripts')

    # 3. Extract and map
    print(f'\n[3] Extracting operator sequences...')
    samples = []
    code_hits = Counter()
    seen_code_sequences = defaultdict(set)  # per-code dedup: track sequences per L3 code
    max_per_code = 500  # max samples per L3 code

    for i, fp in enumerate(scripts):
        if i % 2000 == 0:
            print(f'  Processing {i}/{len(scripts)}... samples={len(samples)}')

        ops = extract_ops_from_py(fp)
        l3_codes = []
        for op in ops:
            l3 = map_op_to_l3(op, qgis_to_l3)
            if l3:
                l3_codes.append(l3)

        if len(l3_codes) < 1 or len(l3_codes) > 12:
            continue

        # Check if any of the codes in this chain still need samples
        needs_more = any(code_hits.get(c, 0) < max_per_code for c in l3_codes)
        if not needs_more:
            continue

        # Per-code dedup: only dedup within each L3 code category
        for c in l3_codes:
            seq_key = tuple(l3_codes)
            if seq_key in seen_code_sequences[c]:
                continue  # already have this exact sequence for this code
            seen_code_sequences[c].add(seq_key)
            code_hits[c] += 1

        sample = {
            'source_file': os.path.basename(fp).replace('.py', '').replace('_converted', ''),
            'source_dir': str(Path(fp).parent),
            'original_ops': ops[:12],
            'l3_codes': l3_codes,
            'chain_len': len(l3_codes),
            'source': 'py_script_vector_mining',
        }
        samples.append(sample)

        # Stop when target codes are filled
        all_filled = all(
            code_hits.get(code, 0) >= min(max_per_code, 300)
            for code in ['L3_02_02_07', 'L3_02_02_05', 'L3_02_02_04', 'L3_02_07_01',
                         'L3_02_05_12', 'L3_02_06_05', 'L3_02_05_06', 'L3_02_06_01',
                         'L3_02_05_11', 'L3_02_02_06', 'L3_02_06_02', 'L3_02_02_01']
        )
        if len(samples) >= 3000 and all_filled:
            break

    print(f'\n  Generated {len(samples)} vector samples')
    print(f'\n  Code hit counts:')
    for code, cnt in code_hits.most_common(20):
        print(f'    {code}: {cnt}')

    # 4. Save
    out = OUTPUT_DIR / 'vector_py_samples.jsonl'
    with open(out, 'w', encoding='utf-8') as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + '\n')
    print(f'\n[DONE] {len(samples)} samples saved to {out}')


if __name__ == '__main__':
    main()
