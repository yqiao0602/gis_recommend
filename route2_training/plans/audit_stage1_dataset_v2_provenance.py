"""Read-only audit for Stage-1 dataset v2 against the frozen Tier A/B pool.
Checks row-level provenance, train split membership, category shares, and the
explicit no-Task-truncation/actual-token budget claims in the builder report.
"""
import collections
import json
from pathlib import Path

DATA='/home/qy/system_redesign/route2_training/plans/stage1_train_v2_2.jsonl'
TIER='/home/qy/system_redesign/route2_training/plans/plan_pool_tiered_v2.jsonl'
SRC='/home/qy/system_redesign/outputs_v2/gee_b1_stage_data_v1/b1_gee_stage_train.jsonl'
REPORT='/home/qy/system_redesign/route2_training/plans/stage1_dataset_report_v2_2.json'

def main():
    tier={}
    for l in open(TIER,encoding='utf-8'):
        r=json.loads(l);tier[r['row_id']]=r['tier']
    srcsplit={}
    for i,l in enumerate(open(SRC,encoding='utf-8'),1):
        srcsplit[i]=json.loads(l).get('split')
    rows=[json.loads(l) for l in open(DATA,encoding='utf-8')]
    cats=collections.Counter(r['cat'] for r in rows)
    bad=[]
    for i,r in enumerate(rows):
        rid=r.get('source_row_id')
        if rid not in tier or tier[rid] not in ('A','B') or srcsplit.get(rid)!='train':
            bad.append({'index':i,'source_row_id':rid,'tier':tier.get(rid),'split':srcsplit.get(rid)})
    rep=json.load(open(REPORT,encoding='utf-8'))
    result={'rows':len(rows),'tierAB_source_rows':sum(t in ('A','B') for t in tier.values()),
            'unique_source_rows_used':len({r['source_row_id'] for r in rows}),
            'categories':dict(cats),'pool_membership_violations':len(bad),
            'violations_sample':bad[:10],
            'actual_token_share':rep['actual_token_share'],
            'task_truncation_count':rep.get('task_truncation_count'),
            'truncation_by_category':rep.get('truncation_by_cat'),
            'chain_lm_examples':rep.get('chain_lm_examples')}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    out=Path(__file__).resolve().parent/'stage1_dataset_provenance_audit_v2_2.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not bad, 'outside Tier A/B or non-train source row found'
    assert rep.get('task_truncation_count')==0
    assert rep.get('chain_lm_examples')==0
    return result

if __name__=='__main__':main()
