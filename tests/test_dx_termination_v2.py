#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-R regression tests: per-item termination must not inherit the batch max.

Covers the owner-mandated case: in ONE batch, one item runs to the cap while
another emits EOS immediately; the two must receive different, correct labels.
Also locks the orthogonality of output_state (empty/non-empty) and term.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from dx_termination_v2 import classify_batch, classify_item, first_stop_index  # noqa: E402


def test_batch_cap_and_immediate_eos_get_distinct_labels():
    texts = ["", "some long reasoning ..."]
    n_items = [2048, 1]           # item A ran to cap; item B stopped at once
    out = classify_batch(texts, n_items, 2048)
    assert out[0]["term"] == "CAP_TRUNC"
    assert out[0]["output_state"] == "empty"
    assert out[1]["term"] == "IMMEDIATE_EOS"
    assert out[1]["output_state"] == "non_empty"
    assert out[0]["term"] != out[1]["term"]


def test_batch_field_is_never_used_for_individual_terms():
    # identical per-item lengths, different texts -> only markers may differ
    out = classify_batch(["no marker", "END OF LIST\nStep 1 ..."], [50, 50], 2048)
    assert out[0]["term"] == "EOS"
    assert out[1]["term"] == "END_MARK"


def test_end_mark_takes_precedence_over_length():
    d = classify_item("NO OPERATOR FOR THIS STEP\nbecause ...", 300, 2048)
    assert d["term"] == "END_MARK"
    assert d["output_state"] == "non_empty"


def test_empty_and_term_are_orthogonal():
    a = classify_item("", 2048, 2048)   # empty text but the item truly hit cap
    assert a["output_state"] == "empty" and a["term"] == "CAP_TRUNC"
    b = classify_item("", 1, 2048)      # empty text, immediate EOS
    assert b["output_state"] == "empty" and b["term"] == "IMMEDIATE_EOS"


def test_first_stop_index_counts_the_stop_token():
    assert first_stop_index([5, 6, 9, 9], {9}, 4) == 3
    assert first_stop_index([5, 6], {9}, 2) == 2
