#!/usr/bin/env python3
"""Run the proposal census without a frozen expected-count profile (calibration only)."""
from pathlib import Path
import argparse
import json
from scripts.build_gee_complete_workflow_expansion_batch import _route_expansion_census, _source_representatives

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--facts', type=Path, required=True)
    p.add_argument('--text', type=Path, required=True)
    p.add_argument('--reviewed', type=Path, required=True)
    p.add_argument('--existing', type=Path, required=True)
    p.add_argument('--mapping', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = _route_expansion_census(
        fact_bundles_path=a.facts,
        task_text_candidates_path=a.text,
        reviewed_packet_path=a.reviewed,
        existing_semantic_rows_path=a.existing,
        id_mappings_path=a.mapping,
        authority_profile_name='gee_batch13_replacement_probe',
        authority_sha256={
            'fact_bundles': '', 'task_text_candidates': '', 'reviewed_packet': '',
            'existing_semantic_rows': '', 'mapping': ''},
    )
    a.out.mkdir(parents=True, exist_ok=True)
    for name, rows in {
        'proposal_candidates.jsonl': result.proposal_rows,
        'remaining_ledger.jsonl': result.remaining_ledger,
        'source_overlap.jsonl': result.source_overlap_sidecar,
        'semantic_failures.jsonl': result.fail_closed_sidecar,
        'duplicates.jsonl': result.duplicate_sidecar,
        'length_sidecar.jsonl': result.length_sidecar,
    }.items():
        (a.out / name).write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows), encoding='utf-8')
    (a.out / 'summary.json').write_text(json.dumps(result.summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    reps = _source_representatives(result.proposal_rows)
    from collections import Counter
    result.summary['source_support'] = dict(Counter(r['risk_stratum'] for r in reps))
    (a.out / 'summary.json').write_text(json.dumps(result.summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result.summary, ensure_ascii=False))
if __name__ == '__main__':
    main()
