#!/usr/bin/env python3
"""Per-class evidence table for 13 new L3 codes.

Reads real sample data and gold annotation, outputs JSON + Markdown artifacts.
Usage:
    python scripts/_evidence_table.py \
        --samples outputs_v2/vocab_expansion_v1/vocab_expansion_raw_samples.jsonl \
        --gold outputs_v2/diagnostics/quality_gate/vector_gold_annotated.csv \
        --output-dir outputs_v2/diagnostics/evidence_table/
"""

import argparse, csv, json, os, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ── 13 new codes ──
NEW_CODES = {
    'L3_02_01_02': {'name': 'Reproject', 'existing_alt': 'No L3 for CRS transform'},
    'L3_02_01_03': {'name': 'Fix Geometries', 'existing_alt': 'No L3 for geometry repair'},
    'L3_02_03_01': {'name': 'Grid', 'existing_alt': 'Vector grid (not raster L3_03_*)'},
    'L3_02_03_02': {'name': 'Simplify', 'existing_alt': 'No L3; similar to Smooth'},
    'L3_02_03_03': {'name': 'Voronoi', 'existing_alt': 'No L3'},
    'L3_02_03_04': {'name': 'Delaunay', 'existing_alt': 'No L3; dual of Voronoi'},
    'L3_02_05_01': {'name': 'Delete Duplicate', 'existing_alt': 'Union+Dissolve combo possible'},
    'L3_02_05_02': {'name': 'Snap', 'existing_alt': 'No L3 for topological snap'},
    'L3_02_05_03': {'name': 'Delete Holes', 'existing_alt': 'Select+Erase combo possible'},
    'L3_02_05_04': {'name': 'Smooth', 'existing_alt': 'No L3; distinct from Simplify'},
    'L3_02_05_05': {'name': 'Concave Hull', 'existing_alt': 'MinBoundingGeom = convex only'},
    'L3_02_07_02': {'name': 'Polygons to Lines', 'existing_alt': 'Geometry type conversion'},
    'L3_02_07_03': {'name': 'Extract Vertices', 'existing_alt': 'FeatureToPoint = centroid only'},
}


def load_samples(path: str) -> list[dict]:
    samples = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def load_gold(path: str) -> set[str]:
    """Return set of L3 codes that appear in gold annotations."""
    needed = set()
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for r in reader:
            gc = r.get('gold_codes', '')
            if gc:
                for c in gc.split(','):
                    c = c.strip()
                    if c in NEW_CODES:
                        needed.add(c)
    return needed


def build_table(samples: list[dict], gold_needed: set[str]) -> list[dict]:
    # Per-code stats
    total_counts = Counter()
    single_counts = Counter()
    for s in samples:
        codes = s.get('l3_codes', [])
        for c in codes:
            if c in NEW_CODES:
                total_counts[c] += 1
                if len(codes) == 1:
                    single_counts[c] += 1

    rows = []
    for code in sorted(NEW_CODES, key=lambda c: total_counts.get(c, 0), reverse=True):
        info = NEW_CODES[code]
        total = total_counts.get(code, 0)
        single = single_counts.get(code, 0)
        sc_rate = single / total if total > 0 else 0.0
        in_gold = 'yes' if code in gold_needed else 'no'

        # Verdict
        if total >= 500 and sc_rate >= 0.10:
            verdict = 'KEEP'
        elif total >= 200:
            verdict = 'REVIEW'
        else:
            verdict = 'DROP'

        rows.append({
            'code': code,
            'name': info['name'],
            'samples': total,
            'single_code_pct': round(sc_rate * 100, 1),
            'gold_need': in_gold,
            'existing_alt': info['existing_alt'],
            'verdict': verdict,
        })
    return rows


def write_artifacts(rows: list[dict], output_dir: str) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # JSON
    with (out / 'evidence_table.json').open('w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # Markdown
    lines = ['# 13 New L3 Codes — Evidence Table', '']
    lines.append('| Code | Name | Samples | Single% | Gold Need | Verdict |')
    lines.append('|------|------|---------|---------|-----------|---------|')
    for r in rows:
        lines.append(
            f'| {r["code"]} | {r["name"]} | {r["samples"]} | '
            f'{r["single_code_pct"]}% | {r["gold_need"]} | **{r["verdict"]}** |'
        )

    # Summary by verdict
    lines.append('')
    lines.append('## Summary')
    keep = [r for r in rows if r['verdict'] == 'KEEP']
    review = [r for r in rows if r['verdict'] == 'REVIEW']
    drop = [r for r in rows if r['verdict'] == 'DROP']
    lines.append(f'- KEEP: {len(keep)} codes')
    for r in keep:
        lines.append(f'  - {r["code"]} ({r["name"]}): {r["samples"]} samples, {r["single_code_pct"]}% single-code')
    lines.append(f'- REVIEW: {len(review)} codes')
    for r in review:
        lines.append(f'  - {r["code"]} ({r["name"]}): {r["samples"]} samples')
    lines.append(f'- DROP: {len(drop)} codes')
    for r in drop:
        lines.append(f'  - {r["code"]} ({r["name"]}): {r["samples"]} samples — {r["existing_alt"]}')

    lines.append('')
    lines.append('## Recommended Activation Candidates (top 3-5 KEEP codes)')
    top = keep[:5]
    for r in top:
        lines.append(f'- {r["code"]} ({r["name"]}): {r["samples"]} samples, {r["single_code_pct"]}% pure')

    with (out / 'evidence_table.md').open('w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print('\n'.join(lines))
    print(f'\nArtifacts written to {out}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', required=True,
                        help='Path to vocab_expansion_raw_samples.jsonl')
    parser.add_argument('--gold', default=None,
                        help='Path to vector_gold_annotated.csv')
    parser.add_argument('--output-dir', default='outputs_v2/diagnostics/evidence_table')
    args = parser.parse_args()

    samples = load_samples(args.samples)
    gold = load_gold(args.gold) if args.gold else set()
    rows = build_table(samples, gold)
    write_artifacts(rows, args.output_dir)


if __name__ == '__main__':
    main()
