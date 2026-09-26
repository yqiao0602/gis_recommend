"""CPU-only regression tests for the frozen Stage-1 preflight stack."""
import contextlib
import json
import random
import sys
import types

import pytest

from route2_training.plans import gate_evaluator_v1
from route2_training.plans.chain_to_plan_v1_1 import convert
from route2_training.plans.stage1_collator import Stage1PlanCollator, TaskTooLongError
from route2_training.plans.stage1_dataset_v2 import corrupt_plan, token_len
from route2_training.plans.build_gate_probes_v3 import w1_samples, w3_sample, w4_samples
from route2_training.plans.gate_evaluator_v1 import (
    parse_family_sequence, parse_plan_intents, score_items, w1_correct, w2_correct,
)


class FakeTokenizer:
    bos_token_id = 1
    eos_token_id = 2
    pad_token_id = 0

    def encode(self, text, add_special_tokens=False):
        ids = [ord(c) % 251 + 3 for c in text]
        return ([self.bos_token_id] + ids + [self.eos_token_id]) if add_special_tokens else ids


def example_plan():
    p, _ = convert('ee.ImageCollection > ee.ImageCollection.filterDate > '
                   'ee.ImageCollection.median > ee.Image.clip')
    return p


def test_task_is_never_truncated_and_token_budget_matches_collator():
    tok = FakeTokenizer()
    col = Stage1PlanCollator(tok, max_len=1024)
    ex = {'task': 'COMPLETE TASK', 'separator': '\nWorkflow plan:',
          'context': 'C' * 1300, 'target': 'PLAN' * 400}
    enc = col.encode_example(ex)
    assert len(enc['input_ids']) == token_len(tok, ex) <= 1024
    assert not enc['task_truncated']
    assert enc['task_tokens'] == len(tok.encode(ex['task']))
    assert enc['context_truncated_tokens'] > 0
    assert enc['target_truncated_tokens'] > 0


def test_overlong_task_fails_closed():
    col = Stage1PlanCollator(FakeTokenizer(), max_len=64)
    try:
        col.encode_example({'task': 'T' * 100, 'separator': '\nPlan:', 'context': '', 'target': 'x'})
    except TaskTooLongError:
        return
    raise AssertionError('complete Task must be preserved by rejecting an overlong sample')


def test_w4_corruptions_are_real_and_label_matches_mutation():
    steps = [
        {'order':1,'intent':'load vectors','family':'VECTOR_LOAD','input':[],
         'output':{'type':'vector'},'depends_on':[],'constraints':{},'roles':[],'provision':True},
        {'order':2,'intent':'rasterize vectors','family':'VECTOR_TO_RASTER','input':[{'role':'primary','type':'vector'}],
         'output':{'type':'raster'},'depends_on':[1],'constraints':{},'roles':['primary'],'provision':False},
        {'order':3,'intent':'smooth raster','family':'NEIGHBORHOOD','input':[{'role':'primary','type':'raster'}],
         'output':{'type':'raster'},'depends_on':[2],'constraints':{},'roles':['primary'],'provision':False},
        {'order':4,'intent':'polygonize raster','family':'RASTER_TO_VECTOR','input':[{'role':'primary','type':'raster'}],
         'output':{'type':'vector'},'depends_on':[3],'constraints':{},'roles':['primary'],'provision':False},
    ]
    seen = set()
    for seed in range(100):
        damaged, repaired, kind = corrupt_plan({'steps': steps}, random.Random(seed))
        assert damaged != repaired
        assert kind in {'delete', 'swap', 'insert'}
        if kind == 'insert':
            assert len(damaged) == len(repaired) + 1
            inserted = next(s for s in damaged if s.get('synthetic_corruption'))
            idx = damaged.index(inserted)
            prev_type = damaged[idx-1]['output']['type']
            assert prev_type not in [x['type'] for x in inserted['input']]
        elif kind == 'delete':
            assert len(damaged) == len(repaired) - 1
        else:
            assert len(damaged) == len(repaired)
            # Swaps are sampled only if the local type transitions become invalid.
            assert any(damaged[j]['output']['type'] not in
                       [x['type'] for x in damaged[j+1]['input']]
                       for j in range(len(damaged)-1)
                       if damaged[j+1]['input'])
        seen.add(kind)
    assert seen == {'delete', 'swap', 'insert'}


def test_w1_gate_probe_contains_roles_and_types():
    plan = example_plan()
    probes = w1_samples(plan['steps'])
    assert probes
    assert all('role:type' in p['prompt'] for p in probes)
    assert all('input_slots' in p['check'] and 'output_type' in p['check'] for p in probes)
    assert all('ee.' not in p['prompt'] for p in probes)


def test_w3_is_open_plan_and_sidecar_is_scoring_only():
    plan = example_plan()
    p = w3_sample('Estimate a temporal raster statistic', plan)
    assert p['target'].startswith('Step 1:')
    assert 'FAMILY_ID' not in p['prompt']
    assert 'SPATIAL_CLIP' not in p['prompt'] and 'SPATIAL_CLIP' not in p['target']
    fams, ok = parse_family_sequence(p['target'], p['intent_family_sidecar'])
    assert ok and fams == p['reference_families']
    intents = parse_plan_intents(p['target'])
    assert len(intents) == len(plan['steps'])


def test_gate_scores_round_trip_and_strict_yes_no():
    plan = example_plan()
    w3 = w3_sample('Estimate a temporal raster statistic', plan)
    w4 = w4_samples(plan['steps'] + [dict(plan['steps'][-1], order=4)], random.Random(3))[0]
    probes = [
        {'capability': 'W1', 'kind': 'op_io',
         'target': 'accepts primary input:raster_collection; produces raster_collection'},
        {'capability': 'W2', 'kind': 'comp_valid', 'target': 'Yes', 'expected': 'Yes'},
        w3,
        {'capability': 'W4', 'kind': w4['kind'], 'target': w4['target'],
         'reference_intents': w4['reference_intents']},
    ]
    outputs = [probes[0]['target'], 'Yes, compatible.', w3['target'], w4['target']]
    scores = score_items(probes, outputs)
    assert scores['macro']['W1'] == 1.0
    assert scores['macro']['W2'] == 1.0
    assert scores['macro']['W3_as_is'] == 1.0
    assert scores['macro']['W4'] == 1.0
    assert w1_correct(outputs[0], probes[0]['target'])
    assert w2_correct('No.', 'No')
    assert not w2_correct('Probably yes', 'No')


@pytest.mark.parametrize('oom_limit, n_probes, batch_size, expected_attempts, expected_halvings', [
    (1, 3, 3, [3, 1, 1, 1], 1),
    (1, 5, 5, [5, 2, 1, 1, 1, 1, 1], 2),
    (2, 2, 2, [2], 0),
])
def test_gate_report_records_actual_batch_halvings(tmp_path, monkeypatch, oom_limit, n_probes,
                                                   batch_size, expected_attempts, expected_halvings):
    class CPUOOM(Exception):
        pass

    class Tensor(list):
        @property
        def shape(self):
            return (len(self), len(self[0]))

    class Batch(dict):
        def to(self, device):
            return self

    class Tokenizer:
        eos_token_id = 2
        pad_token_id = 0
        pad_token = '<pad>'

        def __call__(self, prompts, **kwargs):
            return Batch(input_ids=Tensor([[1] for _ in prompts]))

        def decode(self, ids, skip_special_tokens):
            return 'Yes'

        @classmethod
        def from_pretrained(cls, path):
            return cls()

    attempts = []

    class Model:
        def eval(self):
            return self

        def generate(self, input_ids, **kwargs):
            attempts.append(len(input_ids))
            if len(input_ids) > oom_limit:
                raise CPUOOM('simulated batch OOM')
            return [[1, 2] for _ in input_ids]

        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    class Quantization:
        def __init__(self, **kwargs):
            pass

    torch = types.ModuleType('torch')
    torch.bfloat16 = object()
    torch.cuda = types.SimpleNamespace(OutOfMemoryError=CPUOOM, empty_cache=lambda: None)
    torch.no_grad = contextlib.nullcontext
    transformers = types.ModuleType('transformers')
    transformers.AutoModelForCausalLM = Model
    transformers.AutoTokenizer = Tokenizer
    transformers.BitsAndBytesConfig = Quantization
    peft = types.ModuleType('peft')
    peft.PeftModel = types.SimpleNamespace(from_pretrained=lambda model, path: model)

    probe_file = tmp_path / 'probes.jsonl'
    probes = [{'probe_id': f'dev:{i}', 'capability': 'W2', 'kind': 'comp_valid',
               'prompt': f'Probe {i}', 'target': 'Yes', 'expected': 'Yes'}
              for i in range(n_probes)]
    probe_file.write_text(''.join(json.dumps(p) + '\n' for p in probes), encoding='utf-8')
    out_dir = tmp_path / 'reports'
    monkeypatch.setitem(sys.modules, 'torch', torch)
    monkeypatch.setitem(sys.modules, 'transformers', transformers)
    monkeypatch.setitem(sys.modules, 'peft', peft)
    monkeypatch.setattr(gate_evaluator_v1.signal, 'SIGALRM', 14, raising=False)
    monkeypatch.setattr(gate_evaluator_v1.signal, 'signal', lambda signum, handler: None)
    monkeypatch.setattr(gate_evaluator_v1.signal, 'alarm', lambda seconds: None, raising=False)
    monkeypatch.setattr(sys, 'argv', ['gate_evaluator_v1.py', '--base-model', 'test-base',
                                     '--label', 'base', '--split', 'dev',
                                     '--probe-file', str(probe_file), '--out-dir', str(out_dir),
                                     '--batch-size', str(batch_size)])

    gate_evaluator_v1.main()

    report = json.loads((out_dir / 'gate_report_base_dev.json').read_text(encoding='utf-8'))
    items = [json.loads(line) for line in (out_dir / 'gate_items_base_dev.jsonl').open(encoding='utf-8')]
    assert attempts == expected_attempts
    assert report['batch_halvings'] == expected_halvings
    assert report['oom_single'] == report['timeout'] == 0
    assert report['W2_score'] == 1.0
    assert len(items) == n_probes and all(item['correct'] for item in items)
    assert report['evaluator_version'] == 'gate-eval-v1.3.1'
