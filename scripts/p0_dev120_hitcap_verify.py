#!/usr/bin/env python3
"""hit-cap verification for dev-120 P0 blueprints (owner check):
- definition audit: hit_cap = (gen_tokens >= 384), denominator = all 120 rows
- truncation-pollution dissection: balanced FIRST-object extraction vs greedy
  regex parse, cross-tabbed with hit_cap. If balanced_ok on hit_cap rows,
  the JSON completed BEFORE the cap -> content metrics on parsed rows are
  not truncation-polluted (trailing junk is ignored); parse failures split
  into cap-caused (no balanced object) vs junk-pollution."""
import json, re

def balanced_object(text):
    start = text.find("{")
    if start < 0:
        return None, "no_brace"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        j = json.loads(text[start:i + 1])
                        if isinstance(j, dict) and "stages" in j:
                            return j, "ok"
                        return None, "obj_no_stages"
                    except Exception:
                        return None, "unparseable_balanced"
    return None, "no_close_truncated"

def greedy(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    return j if isinstance(j, dict) and "stages" in j else None

d = json.load(open("/home/qy/p0_dev120_blueprints_v1.json", encoding="utf-8"))
items = d["items"]
n = len(items)
cross = Counter = __import__("collections").Counter()
junk_after_complete = 0
for it in items:
    _, bal = balanced_object(it["pred_text"])
    gok = greedy(it["pred_text"]) is not None
    key = (bal, "greedy_ok" if gok else "greedy_fail",
           "cap" if it["hit_cap"] else "eoss")
    cross[key] += 1
    if bal == "ok" and it["hit_cap"]:
        # complete JSON + trailing generation: is there junk with braces?
        text = it["pred_text"]
        start = text.find("{")
        depth, in_str, esc, end = 0, False, False, -1
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc: esc = False
                elif c == "\\": esc = True
                elif c == '"': in_str = False
            else:
                if c == '"': in_str = True
                elif c == "{": depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
        if end >= 0 and len(text[end + 1:].strip()) > 0:
            junk_after_complete += 1

print("n =", n)
print("hit_cap definition: gen_tokens >= 384 (max_new_tokens), denominator = all rows")
print("hit_cap rows:", sum(it["hit_cap"] for it in items),
      "| mean gen_tokens:", round(sum(it["gen_tokens"] for it in items) / n, 1))
print("cross-tab (balanced_state, greedy, cap):")
for k, v in sorted(cross.items()):
    print("  ", k, v)
print("complete-JSON-but-trailing-junk among hit_cap rows:", junk_after_complete)
