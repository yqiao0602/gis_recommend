"""Stage-1-specific collator: task-preserving, target-loss-only, max_len=1024.

Do NOT reuse QgisGraphCollator: that frozen P0 collator left-truncates the
prompt, while ⑦ requires the Stage-1 Task to remain fully intact.

Input row: {task, context, target, cat}. The complete Task is always kept;
if Task alone cannot fit, raise TaskTooLongError (fail closed, never truncate
Task). Context plan is truncated from its tail first; target is truncated
from its tail last. Labels are masked on Task/context and enabled on target.
"""
class TaskTooLongError(ValueError):
    pass


class Stage1PlanCollator:
    def __init__(self, tokenizer, max_len=1024):
        self.tok = tokenizer
        self.max_len = max_len
        self.sep = '\nWorkflow plan:'

    def encode_example(self, row):
        task_ids = self.tok.encode(row['task'], add_special_tokens=False)
        separator_ids = self.tok.encode(row.get('separator', self.sep), add_special_tokens=False)
        context_ids = self.tok.encode(row.get('context', ''), add_special_tokens=False)
        target_body = self.tok.encode(' ' + row['target'], add_special_tokens=False)
        bos = [self.tok.bos_token_id] if self.tok.bos_token_id is not None else []
        eos = [self.tok.eos_token_id] if self.tok.eos_token_id is not None else []
        fixed = len(bos) + len(task_ids) + len(separator_ids)
        if fixed >= self.max_len:
            raise TaskTooLongError(f"task+separator uses {fixed}/{self.max_len} tokens")
        room = self.max_len - fixed
        # Preserve the complete task. Context/plan is tail-truncated before target.
        context_truncated = 0
        target_truncated = 0
        if len(context_ids) + len(target_body) + len(eos) > room:
            keep_context = max(0, room - len(eos) - min(len(target_body), max(0, room // 2)))
            if len(context_ids) > keep_context:
                context_truncated = len(context_ids) - keep_context
                context_ids = context_ids[:keep_context]
        target_room = max(0, room - len(context_ids) - len(eos))
        if len(target_body) > target_room:
            target_truncated = len(target_body) - target_room
            target_body = target_body[:target_room]
        target_ids = target_body + eos
        prefix = bos + task_ids + separator_ids + context_ids
        input_ids = prefix + target_ids
        labels = [-100] * len(prefix) + target_ids
        return {
            'input_ids': input_ids, 'labels': labels,
            'attention_mask': [1] * len(input_ids),
            'task_tokens': len(task_ids), 'context_tokens': len(context_ids),
            'target_tokens': len(target_body),
            'context_truncated_tokens': context_truncated,
            'target_truncated_tokens': target_truncated,
            'task_truncated': False,
        }

    def __call__(self, batch):
        enc = [self.encode_example(r) for r in batch]
        maxlen = max(len(e['input_ids']) for e in enc)
        pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id
        for e in enc:
            n = maxlen - len(e['input_ids'])
            e['input_ids'] += [pad] * n
            e['labels'] += [-100] * n
            e['attention_mask'] += [0] * n
        return {k: [e[k] for e in enc] for k in
                ('input_ids', 'labels', 'attention_mask', 'task_tokens',
                 'context_tokens', 'target_tokens', 'target_truncated_tokens',
                 'task_truncated')}
