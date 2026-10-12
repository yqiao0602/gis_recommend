#!/usr/bin/env python3
"""Parse-failure dissection: greedy-regex vs balanced-brace extraction.
Classifies each prediction: complete JSON+stages (balanced), junk-polluted
(complete object exists but greedy regex would fail), truly truncated
(no closing brace), or no brace at all."""
import json, re

def balanced_object(text):
    start = text.find('{')
    if start < 0:
        return None, 'no_brace'
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    frag = text[start:i + 1]
                    try:
                        j = json.loads(frag)
                        if isinstance(j, dict) and 'stages' in j:
                            return j, 'ok'
                        return None, 'obj_no_stages'
                    except Exception:
                        return None, 'unparseable_balanced'
    return None, 'no_close_truncated'

def greedy_parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    return j if isinstance(j, dict) and "stages" in j else None

for name, path in [("P0", "/home/qy/p0_fmt_dev_preds_rec.json"),
                   ("P1", "/home/qy/p1_dev_full_preds_rec.json"),
                   ("P2", "/home/qy/p2_dev_full_preds.json")]:
    d = json.load(open(path, encoding="utf-8"))
    items = d["items"]
    n = len(items)
    cats = {"ok": 0, "obj_no_stages": 0, "unparseable_balanced": 0,
            "no_close_truncated": 0, "no_brace": 0}
    greedy_ok = 0
    for it in items:
        j, why = balanced_object(it["pred_text"])
        cats[why] += 1
        if greedy_parse(it["pred_text"]) is not None:
            greedy_ok += 1
    print(name, json.dumps(cats),
          "| balanced_rate:", round(cats["ok"] / n, 4),
          "| greedy_rate:", round(greedy_ok / n, 4))
