"""Rewrite each selected Gate-v3 W3 task prompt for answer-echo counter.

The API sees only the task text, never the gold plan/target. Original
probe IDs are preserved; output maps exact probe_id -> rewritten task.
RW_KEY is environment-only; no credential persistence.
"""
import json, os, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://token-unlimited.com/v1/chat/completions'
MODEL = 'gpt-6-luna'
SYS = ('Rewrite this GIS task description in different wording while preserving exactly the same objective, '
       'data sources, constraints, regions, time ranges, outputs, and implied workflow intent. '
       'Do not add or remove requirements. Do not mention any software library, API, provider, or algorithm ID. '
       'Keep the original language. Output only the rewritten task text.')

def rewrite_one(task, key):
    body = json.dumps({'model': MODEL, 'messages': [
        {'role':'system','content':SYS}, {'role':'user','content':task}],
        'max_completion_tokens':800}).encode()
    req = urllib.request.Request(URL,data=body,headers={
        'Content-Type':'application/json','Authorization':'Bearer '+key})
    last=''
    for a in range(8):
        try:
            with urllib.request.urlopen(req,timeout=120) as r: d=json.loads(r.read())
            out=d['choices'][0]['message']['content'].strip()
            if len(out)<20 or out.strip().lower()==task.strip().lower(): raise ValueError('empty/equal rewrite')
            if re.search(r'\bee\.[A-Za-z]|\b(native|gdal|grass7?|saga|otb|qgis)\s*:',out,re.I): raise ValueError('identity mention')
            return key,out,None
        except Exception as e:
            last=str(e)[:120];time.sleep(min(12*(a+1),90))
    return key,None,last

def main():
    key=os.environ.get('RW_KEY','')
    if not key: raise SystemExit('RW_KEY missing')
    d=ROOT/'docs/reports/route2_p0_contract/plan_pipeline_v1'
    probes=[]
    for split in ('dev','test'):
        for line in (d/f'gate_{split}_probes_v3.jsonl').open(encoding='utf-8'):
            p=json.loads(line)
            if p['capability']=='W3' and p['kind']=='plan_gen':
                task=p['prompt'].split('\nWorkflow plan:',1)[0]
                probes.append((p['probe_id'],task))
    done={};fail=[]
    with ThreadPoolExecutor(3) as ex:
        futures={ex.submit(rewrite_one,t,k):k for k,t in probes}
        for j,fu in enumerate(as_completed(futures),1):
            k,text,err=fu.result()
            if text:done[k]=text
            else:fail.append({'probe_id':k,'reason':err})
            if j%50==0:print(f'{j}/{len(probes)} accepted={len(done)} rejected={len(fail)}',flush=True)
    out=d/'gate_v3_rewrites.json'
    out.write_text(json.dumps({'rewrites':done,'failures':fail},ensure_ascii=False,indent=1),encoding='utf-8')
    print(f'W3 probes={len(probes)} rewritten={len(done)} failed={len(fail)} -> {out}')
if __name__=='__main__':main()
