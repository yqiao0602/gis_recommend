"""W3 instruction rewriter via owner-provided endpoint (gpt-6-luna).

Answer-echo counter for the Capability Gate: paraphrase gate W3 task
instructions so surface wording differs while workflow semantics are
preserved 1:1 (same operations, same order, no additions/removals).

Key handling: read from env RW_KEY only - never written to disk.
Output: rewritten_instructions_v1.json keyed by probe index.
"""
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
URL = 'https://token-unlimited.com/v1/chat/completions'
MODEL = 'gpt-6-luna'
KEY = os.environ.get('RW_KEY', '')
WORKERS = 3
MAX_TRY = 8

SYS = ('You are a precise paraphrasing assistant for GIS workflow task descriptions. '
       'Rewrite the task description with DIFFERENT wording (different sentence structure '
       'and vocabulary) while preserving EXACTLY the same workflow semantics: same data '
       'sources, same operations in the same order, same constraints, same outputs. '
       'Do not add, remove, or reorder any operation. Do not mention any software library, '
       'provider, or API name. Keep the same language as the original. Output ONLY the '
       'rewritten description, nothing else.')


def call(task: str) -> str:
    body = json.dumps({'model': MODEL, 'messages': [
        {'role': 'system', 'content': SYS},
        {'role': 'user', 'content': task}], 'max_completion_tokens': 800}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {KEY}'})
    last = ''
    for attempt in range(MAX_TRY):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            return d['choices'][0]['message']['content'].strip()
        except Exception as e:
            last = str(e)[:120]
            time.sleep(min(20 * (attempt + 1), 120))
    raise RuntimeError(f'failed after {MAX_TRY} tries: {last}')


def valid(orig: str, rw: str) -> bool:
    if not rw or len(rw) < 20 or len(rw) > 4 * len(orig) + 200:
        return False
    if rw.strip().lower() == orig.strip().lower():
        return False
    if re.search(r'\bee\.[A-Za-z]|\b(native|gdal|grass7?|saga|otb|qgis)\s*:', rw, re.I):
        return False
    return True


def main() -> int:
    if not KEY:
        print('RW_KEY env not set'); return 1
    tasks = []
    for sp in ['dev', 'test']:
        for i, line in enumerate((BASE / f'docs/reports/route2_p0_contract/plan_pipeline_v1/'
                                  f'gate_{sp}_probes_v1.jsonl').open(encoding='utf-8')):
            r = json.loads(line)
            if r['capability'] == 'W3':
                tasks.append({'key': f'{sp}:{i}', 'sp': sp, 'idx': i,
                              'task': r['prompt'].replace('\nWorkflow plan:', '').strip()})
    print(f'W3 tasks to rewrite: {len(tasks)}')
    done, failed = {}, []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(call, t['task']): t for t in tasks}
        for n, fut in enumerate(as_completed(futs), 1):
            t = futs[fut]
            try:
                rw = fut.result()
                if valid(t['task'], rw):
                    done[t['key']] = rw
                else:
                    failed.append(t['key'])
            except Exception as e:
                failed.append(t['key'])
            if n % 50 == 0:
                print(f'{n}/{len(tasks)} done, failed {len(failed)}', flush=True)
    (BASE / 'docs/reports/route2_p0_contract/plan_pipeline_v1/rewritten_instructions_v1.json').write_text(
        json.dumps(done, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rewritten: {len(done)} | failed: {len(failed)} | keys saved (no key on disk)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
