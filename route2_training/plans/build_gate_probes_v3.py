"""Build frozen W1-W4 capability-gate probes v3 from author-disjoint splits.

W3 is an open-vocabulary Workflow Plan. FAMILY sidecars are evaluator-only.
As-is and rewritten W3 probes are exact pairs: legacy W3 base probes are
retained byte-for-byte (their 492 rewrite texts were generated from them).
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from route2_training.plans.chain_to_plan_v1_1 import convert, render_plan
from route2_training.plans.stage1_dataset_v2 import corrupt_plan

SRC = '/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train_v1.jsonl'
# Actual frozen source filename differs; fallback is resolved in main.
REPO = Path(__file__).resolve().parents[2]
OUTDIR = REPO / 'docs/reports/route2_p0_contract/plan_pipeline_v1'
PAIRMAP = OUTDIR / 'w3_rewrite_pairmap_v1.json'
OLD_PROBE_DIRS = [OUTDIR, Path(__file__).resolve().parent]
SEED = 20260924
CAP = 3000


def w1_samples(steps):
    out, seen = [], set()
    for s in steps:
        slots = [f"{i['role']}:{i['type']}" for i in s['input']]
        inp = ' | '.join(slots) if slots else 'none'
        outp = s['output']['type'] or 'unspecified'
        key = (s['intent'], tuple(slots), outp)
        if key in seen:
            continue
        seen.add(key)
        out.append({'capability':'W1','kind':'op_io',
                    'prompt':(f'A workflow step is described as: {s["intent"]}.\n'
                              'Answer exactly: accepts <input slot role:type list>; produces <output type>.'),
                    'target':f'accepts {inp}; produces {outp}',
                    'check':{'input_slots':slots,'output_type':outp}})
    return out


def w2_samples(steps):
    out=[]
    for a,b in zip(steps,steps[1:]):
        if a.get('branch') or b.get('branch'): continue
        at=a['output']['type'] or 'unspecified'
        accepted=[x['type'] for x in b['input']]
        bt=', '.join(accepted) or 'unspecified'
        legal=at in accepted if accepted else True
        ans='Yes' if legal else 'No'
        out.append({'capability':'W2','kind':'comp_valid',
                    'prompt':f'Operation 1 "{a["intent"]}" produces {at}. Operation 2 "{b["intent"]}" accepts {bt}. Can operation 2 directly consume operation 1 output? Answer Yes or No.',
                    'target':ans,'expected':ans,
                    'check':{'legal':legal,'prev_output_type':at,'next_accepted_types':accepted}})
    pos=[p for p in out if p['target']=='Yes'];neg=[p for p in out if p['target']=='No']
    n=min(len(pos),len(neg));keep=n+max(0,len(pos)-n)//3
    return pos[:keep]+neg[:keep]


def w3_sample(task,plan):
    fams=[s['family'] for s in plan['steps']]
    side=defaultdict(set)
    for s in plan['steps']:side[s['intent'].strip().lower()].add(s['family'])
    return {'capability':'W3','kind':'plan_gen','prompt':task+'\nWorkflow plan:',
            'target':render_plan(plan),'reference_families':fams,
            'intent_family_sidecar':{k:sorted(v) for k,v in side.items()},
            'check':{'seq':fams}}


def w4_samples(steps,rng):
    damaged,repaired,kind=corrupt_plan({'steps':steps},rng)
    return [{'capability':'W4','kind':'repair_'+kind,
             'prompt':'Repair the structurally inconsistent workflow plan. Output the complete corrected plan.\n'+render_plan({'steps':damaged}),
             'target':render_plan({'steps':repaired}),
             'reference_families':[s['family'] for s in repaired],
             'reference_intents':[s['intent'] for s in repaired],
             'intent_family_sidecar':{s['intent'].strip().lower():[s['family']] for s in repaired},
             'check':{'corruption':kind}}]


def find_legacy(split):
    for d in OLD_PROBE_DIRS:
        p=d/f'gate_{split}_probes_v1.jsonl'
        if p.exists():return p
    raise FileNotFoundError(f'frozen legacy W3 probes missing for {split}')


def main():
    src=Path(SRC)
    if not src.exists():src=Path('/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl')
    pairmap=json.loads(PAIRMAP.read_text(encoding='utf-8'))['pairs'] if PAIRMAP.exists() else {}
    splits={'dev':[],'test':[]}
    for line in src.open(encoding='utf-8'):
        r=json.loads(line)
        if r.get('split')=='val':splits['dev'].append(r)
        elif r.get('split')=='test':splits['test'].append(r)
    report={}
    for split,rows in splits.items():
        rng=random.Random(SEED+(split=='test'));non_w3=[];converted=0; w3_sidecars={}
        for row in rows:
            plan,_=convert(row.get('gee_canonical_chain') or '')
            if plan is None:continue
            converted+=1
            task=row.get('instruction','')
            side={}
            for step in plan['steps']:
                side.setdefault(step['intent'].strip().lower(),set()).add(step['family'])
            w3_sidecars[render_plan(plan)]=(row.get('wid'),{k:sorted(v) for k,v in side.items()})
            batch=w1_samples(plan['steps'])+w2_samples(plan['steps'])+w4_samples(plan['steps'],rng)
            for p in batch:p['source_row_id']=row.get('wid')
            non_w3.extend(batch)
        # Keep the immutable as-is W3 probe set that backs the rewrite experiment.
        legacy=[]
        for line in find_legacy(split).open(encoding='utf-8'):
            p=json.loads(line)
            if p.get('capability')!='W3' or p.get('kind')!='plan_gen':continue
            key=(split,p['prompt'].split('\\nWorkflow plan:',1)[0],p['target'])
            found=w3_sidecars.get(key[2])
            if not found:
                raise RuntimeError(f'{split}: frozen W3 probe not source-verified: {key[1][:80]}')
            wid,side=found
            q=dict(p);q['source_row_id']=wid;q['intent_family_sidecar']=side
            legacy.append(q)
        if not legacy:raise RuntimeError(f'{split}: empty legacy W3 set')
        capacity=max(0,CAP-len(legacy))
        if len(non_w3)>capacity:non_w3=rng.sample(non_w3,capacity)
        base=non_w3+legacy;rng.shuffle(base)
        final=[];n_rw=0
        for i,p0 in enumerate(base):
            p=dict(p0);p['probe_id']=f'{split}:{i}';final.append(p)
            if p['capability']=='W3':
                task=p['prompt'].split('\nWorkflow plan:',1)[0]
                k=f'{split}\t{task}\t{p["target"]}'
                rw=pairmap.get(k)
                if isinstance(rw,dict): rw=rw.get('rewrite')
                if rw:
                    q=dict(p);q['kind']='plan_gen_rewritten';q['probe_id']+=':rewrite'
                    q['prompt']=rw+'\nWorkflow plan:';q['rewrite_of']=p['probe_id'];final.append(q);n_rw+=1
        out=OUTDIR/f'gate_{split}_probes_v3.jsonl'
        out.write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in final),encoding='utf-8')
        report[split]={'rows':len(rows),'plans_converted':converted,'non_w3_probes':len(non_w3),
                       'frozen_w3_base':len(legacy),'rewrite_pairs_joined':n_rw,'total_probes':len(final),
                       'by_capability_kind':dict(Counter(f"{p['capability']}:{p['kind']}" for p in final)),
                       'probe_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
    (OUTDIR/'gate_build_report_v3.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
