#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compact digest of A1 dossier files for adjudication: task step, selections,
changed-card texts, both decision sections (trimmed)."""
import re
import sys
from pathlib import Path

P = Path(r"E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/a1_short/A1_FULL_EVIDENCE_PACKET_V1")


def digest(key, card_cap=1200, dec_cap=1500):
    f = next(P.glob(f"*_{key.replace('#', '_')}.md"))
    t = f.read_text(encoding="utf-8")
    out = [f"===== {key} ====="]
    m = re.search(r"\*\*Step (\d+)\*\*：(.+)", t)
    if m:
        out.append("STEP: " + m.group(2)[:400])
    m = re.search(r"## 候选集合.*?\n(.*?)\n## ", t, re.S)
    if m:
        out.append("TOP10: " + " ".join(x.strip() for x in m.group(1).splitlines() if x.strip()))
    m = re.search(r"- 对照选择：(.*?)｜ 实验选择：(.*)", t)
    if m:
        out.append(f"SEL: control={m.group(1)} | exp={m.group(2)}")
    for label in ("对照臂 (v0_4) 完整决策段", "实验臂 (v0_5) 完整决策段"):
        mm = re.search(re.escape(label) + r"\n```\n(.*?)\n```", t, re.S)
        if mm:
            body = mm.group(1).strip()
            if len(body) > dec_cap:
                body = body[:dec_cap // 2] + "\n...[mid omitted]...\n" + body[-dec_cap // 2:]
            out.append(f"[{label}]\n{body}")
    return "\n".join(out)


if __name__ == "__main__":
    for key in sys.argv[1:]:
        print(digest(key))
        print()
