"""Rebind W3 rewrites to exact legacy (split, task, plan) pairs.
Duplicate pairs with conflicting rewrites keep the lexicographically earliest
probe key; conflicts are reported and not silently overwritten.
"""
import hashlib
import json
from pathlib import Path
BASE = Path(__file__).resolve().parents[2]
D = BASE / 'docs/reports/route2_p0_contract/plan_pipeline_v1'
rw = json.loads((D/'rewritten_instructions_v1.json').read_text(encoding='utf-8'))
out, conflicts = {}, []
for split in ('dev','test'):
    src = D / f'gate_{split}_probes_v1.jsonl'
    for idx,line in enumerate(src.open(encoding='utf-8')):
        key=f'{split}:{idx}'
        if key not in rw: continue
        p=json.loads(line)
        if p.get('capability')!='W3': continue
        task=p['prompt'].split('\nWorkflow plan:',1)[0]
        pair=f'{split}\t{task}\t{p["target"]}'
        if pair in out:
            if out[pair]['rewrite'] != rw[key]:
                conflicts.append({'pair_sha256':hashlib.sha256(pair.encode()).hexdigest(),
                                  'kept':out[pair]['source_probe_id'],'dropped':key})
            continue
        out[pair]={'source_probe_id':key,'rewrite':rw[key]}
path=D/'w3_rewrite_pairmap_v1.json'
path.write_text(json.dumps({'pairs':out,'conflicts':conflicts},ensure_ascii=False,indent=1),encoding='utf-8')
print('pairs',len(out),'conflicting duplicate paraphrases dropped',len(conflicts),'->',path)
