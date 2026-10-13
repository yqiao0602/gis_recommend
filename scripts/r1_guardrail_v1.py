#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R1 structural-cycle guardrail — deployable rule module (v1, frozen).

Shared by offline diagnostics (A′) and decode-time deployment
(run_p0_r1_regression_v1.py StoppingCriteria). Rule params FROZEN from A′:
period 1..6, min 3 consecutive identical cycles, stage-boundary only.

Deployment semantics (owner 2026-10-12):
  - inference-layer reliability guardrail with on/off switch — NOT a
    planning-capability fix
  - truncating unbounded generation to a parseable prefix is NOT workflow
    generation improvement and must never be reported as such
"""
import re

P_MAX = 6
R_MIN = 3
STAGE_RX = re.compile(
    r'\{\s*"seq"\s*:\s*(\d+)\s*,\s*"family"\s*:\s*"([A-Z_]+)"\s*,\s*'
    r'"repeat"\s*:\s*(\d+)\s*\}')


def extract_stages(text):
    st = []
    for m in STAGE_RX.finditer(text or ""):
        st.append({"seq": int(m.group(1)), "family": m.group(2),
                   "repeat": int(m.group(3)), "end": m.end()})
    return st


def rule_fire(st):
    """Return (fired, cut_stage_index, period). Cut keeps the FIRST cycle of
    the last 3 identical cycles (drop repeats 2..3)."""
    k = len(st)
    for p in range(1, P_MAX + 1):
        if k < p * R_MIN:
            continue
        cyc = [tuple((s["family"], s["repeat"]) for s in
                     st[k - p * R_MIN + j * p: k - p * R_MIN + (j + 1) * p])
               for j in range(R_MIN)]
        if cyc[0] == cyc[1] == cyc[2]:
            return True, k - p * (R_MIN - 1), p
    return False, None, None


def cut_text(text):
    """Offline canonical cut: returns (fired, cut_text_or_None, kept_n)."""
    st = extract_stages(text)
    fired, cut_k, _ = rule_fire(st)
    if not fired:
        return False, None, len(st)
    cut_pos = st[cut_k - 1]["end"]
    return True, text[:cut_pos].rstrip().rstrip(","), cut_k
