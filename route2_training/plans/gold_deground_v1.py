"""⑥-5-2 Gold de-grounding pipeline (diagnostic line infrastructure).

Builds Gold-derived Plans from QGIS gold graphs for the DIAGNOSTIC /
upper-bound line ONLY (never main training data). Deterministic:

  gold process (operator_id)
    -> semantic family   (oracle MAP for 148 test ops, keyword rules beyond)
    -> intent            (family phrase, platform-neutral)
    -> typed I/O         (Profile Layer A/B)
    -> order             (topological over gold links; ties by process id)
    -> constraints       (presence-only booleans per B2_SCHEMA_v1)

Leakage audit per plan:
  R-scan  : provider / algorithm-id regex
  recover : candidate set = catalog ops with identical de-grounded
            signature; |set| == 1 -> recoverable -> FAIL flag
  Constraints are presence-only so no value leakage by construction.
"""
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / 'scripts'))
sys.path.insert(0, str(BASE))
from build_route2_semantic_oracle_v1 import MAP  # noqa: E402
from build_audit_a_v1 import FAMILY_PHRASE  # noqa: E402

PROFILE = BASE / 'route2_training/profile/qgis_operator_capability_profile_v0_4.json'
GOLD = BASE / 'docs/reports/route2_p0_contract/test111_final_v1/v2a_A_test.gold.jsonl'
OUT = BASE / 'docs/reports/route2_p0_contract/plan_pipeline_v1/gold_derived_plans_v1.jsonl'

ID_RE = re.compile(r'\b(native|gdal|grass7?|saga|otb|qgis)\s*:', re.I)
PROV_RE = re.compile(r'\b(gdal|grass|saga|otb)\b', re.I)


def topo_order(processes, links):
    ids = [p['process_id'] for p in processes]
    succ = defaultdict(list)
    indeg = {i: 0 for i in ids}
    for l in links:
        s, t = l['source_process_id'], l['target_process_id']
        succ[s].append(t)
        indeg[t] += 1
    q = deque(sorted(i for i in ids if indeg[i] == 0))
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in sorted(succ[u]):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    leftover = [i for i in ids if i not in set(order)]
    return order + sorted(leftover)  # cycles -> deterministic append (flagged)


def main() -> int:
    profile = {k: v for k, v in json.loads(
        PROFILE.read_text(encoding='utf-8')).items() if not k.startswith('_')}
    # signature -> catalog ops (recoverability test)
    sig_index = defaultdict(set)
    for oid, op in profile.items():
        b = op.get('layer_b_params') or {}
        s = (tuple(op.get('input_types_norm') or ()),
             tuple(op.get('output_types_norm') or ()),
             tuple(sorted(p['name'] for p in b.get('parameters', []))))
        sig_index[s].add(oid)

    out_rows, flags = [], []
    for line in GOLD.open(encoding='utf-8'):
        row = json.loads(line)
        order = topo_order(row['processes'], row['links'])
        cyclic = len(order) != len(row['processes'])
        by_id = {p['process_id']: p for p in row['processes']}
        steps, prev_sig = [], None
        for n, pid in enumerate(order, 1):
            op = profile[by_id[pid]['operator_id']]
            fam = MAP.get(by_id[pid]['operator_id'], 'OTHER_UNMAPPED')
            phrase = FAMILY_PHRASE.get(fam, fam.lower().replace('_', ' '))
            b = op.get('layer_b_params') or {}
            s = (tuple(op.get('input_types_norm') or ()),
                 tuple(op.get('output_types_norm') or ()))
            cons = {}
            if fam == 'TEMPORAL_FILTER':
                cons['date constraint'] = True
            if fam == 'AGGREGATION':
                cons['statistic'] = True
            if fam == 'BAND_SELECT':
                cons['band selector'] = True
            steps.append({
                'order': n, 'intent': phrase, 'family': fam,
                'input': [{'type': t} for t in s[0]],
                'output': {'type': s[1]},
                'depends_on': [n - 1] if n > 1 else [],
                'constraints': cons})
            prev_sig = s
        text = json.dumps(steps, ensure_ascii=False)
        # recoverability: how many catalog ops share each step's full signature
        recov_min = min(len(sig_index[(tuple(st['input'][i]['type'] for i in range(len(st['input']))),
                                       (st['output']['type'],),
                                       tuple(sorted(p['name'] for p in
                                            profile[by_id[order[st['order']-1]]['operator_id']][
                                                'layer_b_params']['parameters'])))])
                        for st in steps) if steps else 0
        leak = {'R_scan_provider_id': bool(ID_RE.search(text) or PROV_RE.search(text)),
                'cyclic_source': cyclic,
                'recoverability_min_candidates': recov_min}
        if leak['R_scan_provider_id'] or cyclic or recov_min == 1:
            flags.append({'wid': row['wid'], **leak})
        out_rows.append({'wid': row['wid'],
                         'gold_derived_plan': {'steps': steps},
                         'leakage': leak})

    OUT.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in out_rows),
                   encoding='utf-8')
    n_recov1 = sum(1 for r in out_rows if r['leakage']['recoverability_min_candidates'] == 1)
    print(json.dumps({
        'plans': len(out_rows),
        'R_scan_leak_plans': sum(1 for r in out_rows if r['leakage']['R_scan_provider_id']),
        'cyclic_source_plans': sum(1 for r in out_rows if r['leakage']['cyclic_source']),
        'plans_with_recoverable_step': n_recov1,
        'flagged': len(flags),
    }, ensure_ascii=False, indent=1))
    print(f'written: {OUT}')
    return 0


if __name__ == '__main__':
    main()
