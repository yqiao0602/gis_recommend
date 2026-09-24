#!/usr/bin/env python3
"""DC-1: trie structured decoding for route-2 P:/L: format (spec 2a3c84a).

Modes:
  gold-walk  (CPU): every gold test target must be accepted token-by-token
                    by the grammar matcher before any generation is allowed
                    (Gate B-revised discipline).
  generate   (GPU): constrained greedy generation, single variable vs the
                    frozen DC-0 baseline = the mask itself.

Constraint scope (identical to V2a-P2 v1): format grammar + operator catalog.
No link/DAG constraints. FOUR P2 LESSONS ENFORCED:
  1. EOS explicitly allowed at every step: mask |= EOS after each fill —
     stop control is never touched (the deliberate difference from P2;
     hit_cap rising = red-line design flaw, pre-registered).
  2. Operator names emitted as a NESTED prefix trie (xgrammar 0.1.29 FSM
     state-merge bug across flat alternations).
  3. TokenizerInfo/mask sized to the model embedding dimension, not
     len(tokenizer).
  4. Gold-walk gate precedes any generation.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[1]
BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
SUFFIX = "\nQGIS workflow:"


def emit_trie(rules, counter, words):
    """Nested prefix trie over `words`; each node its own rule (P2 pattern)."""
    root = {}
    for w in words:
        d = root
        for ch in w:
            d = d.setdefault(ch, {})
        d[""] = True

    def emit(d):
        rid = "t%d" % counter[0]
        counter[0] += 1
        alts = []
        if d.get("") is True:
            alts.append('""')
        for ch in sorted(k for k in d if k != ""):
            alts.append('"%s" %s' % (ch, emit(d[ch])))
        rules.append("%s ::= %s" % (rid, " | ".join(alts) if alts else '""'))
        return rid

    return emit(root)


def build_ebnf(catalog):
    ops = sorted(set(catalog))
    for o in ops:
        assert '"' not in o and "\\" not in o and "\n" not in o, o
    rules = []
    counter = [0]
    opname = emit_trie(rules, counter, ops)
    head = [
        'root ::= " "? unit (" " unit)*',
        'unit ::= punit | lunit',
        'punit ::= "P:" pid ":" %s' % opname,
        'lunit ::= "L:" pid ">" pid',
        'pid ::= [a-zA-Z0-9_\\-]+',
    ]
    return "\n".join(head + rules)


def load_catalog():
    cat = json.loads((REPO / "benchmarks/qgis_planner_v1/authority/"
                      "qgis_catalog.json").read_text(encoding="utf-8"))
    return sorted({o["operator_id"] for o in cat["operators"]})


def gold_targets():
    import sys as _s
    _s.path.insert(0, str(REPO))
    from route2_training.harness import graph_to_text
    path = None
    for p in (REPO / "docs/reports/v2a_manifest/v2a_A_test.jsonl",
              Path("/home/qy/gee_llm_smoke/v2a_A_test.jsonl")):
        if p.exists():
            path = p
            break
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        out.append({"wid": r["wid"], "task": r["task_text"],
                    "target": graph_to_text(r["processes"], r["links"])})
    return out


def mode_gold_walk(tok, matcher_proto, rows):
    matcher = matcher_proto()
    ok = 0
    failures = []
    for r in rows:
        ids = tok(" " + r["target"], add_special_tokens=False)["input_ids"]
        bad = None
        for t in ids:
            if not matcher.accept_token(int(t)):
                bad = int(t)
                break
        if bad is None:
            ok += 1
        else:
            failures.append({"wid": r["wid"], "rejected_token": bad,
                             "decoded": tok.decode([bad])})
        matcher.reset()
    print("[gold-walk] accepted %d/%d" % (ok, len(rows)))
    if failures:
        print(json.dumps(failures[:5], ensure_ascii=False, indent=1))
    return 0 if not failures else 1


def mode_generate(args, tok, base, model, matcher_proto, eos_ids, model_vocab):
    import xgrammar as xgr

    rows = gold_targets()
    if args.limit:
        rows = rows[:args.limit]

    class DCConstraint:
        def __init__(self):
            self.matcher = matcher_proto()
            self.bm = None
            self.offset = None

        def __call__(self, input_ids, scores):
            import xgrammar as xgr
            ids = input_ids[0].tolist()
            if self.offset is None:
                self.offset = len(ids)
            while self.offset < len(ids):
                t = int(ids[self.offset])
                if t in eos_ids:
                    self.offset = len(ids)
                    break
                if not self.matcher.accept_token(t):
                    raise RuntimeError(
                        "grammar rejected a token chosen under its own mask")
                self.offset += 1
            self.matcher.fill_next_token_bitmask(self.bm, 0)
            for e in eos_ids:                       # LESSON 1: EOS always legal
                self.bm[0, e // 32] |= (1 << (e % 32))
            xgr.apply_token_bitmask_inplace(scores, self.bm.to(scores.device))
            return scores

    preds = []
    t0 = time.time()
    for i, r in enumerate(rows):
        import xgrammar as xgr
        prompt = r["task"] + SUFFIX
        enc = tok(prompt, return_tensors="pt", truncation=True,
                  max_length=768).to("cuda:0")
        con = DCConstraint()
        con.bm = xgr.allocate_token_bitmask(1, model_vocab)
        gen = model.generate(**enc, max_new_tokens=args.max_new_tokens,
                             do_sample=False, eos_token_id=eos_ids,
                             pad_token_id=tok.pad_token_id,
                             logits_processor=[con])
        cont = gen[0][enc["input_ids"].shape[1]:]
        preds.append({"wid": r["wid"], "raw": tok.decode(cont, skip_special_tokens=True),
                      "n_gen_tokens": int(cont.shape[0])})
        if (i + 1) % 10 == 0:
            print("[gen] %d/%d (%.1f min)" % (i + 1, len(rows),
                                              (time.time() - t0) / 60), flush=True)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / ("v2a_%s_predictions.jsonl" % args.tag)
    dest.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n"
                            for p in preds), encoding="utf-8")
    print("wrote", dest)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["gold-walk", "generate"], required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--tag", default="dc1")
    ap.add_argument("--out-dir", default=str(REPO / "gate2_eval"))
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import torch  # noqa: F401
    from transformers import AutoTokenizer
    import xgrammar as xgr

    catalog = load_catalog()
    ebnf = build_ebnf(catalog)
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    eos_ids = [x for x in (tok.eos_token_id, tok.pad_token_id) if x is not None]
    rows = gold_targets()

    if args.mode == "gold-walk":
        # matcher only needs to cover tokenizer ids (gold tokens are all < len)
        ti = xgr.TokenizerInfo.from_huggingface(
            tok, vocab_size=len(tok) + 8, stop_token_ids=eos_ids)
        cg = xgr.GrammarCompiler(ti).compile_grammar(xgr.Grammar.from_ebnf(ebnf))
        return mode_gold_walk(tok, lambda: xgr.GrammarMatcher(cg), rows)

    # generate: LESSON 3 — compile with the MODEL's embedding dimension
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                device_map="cuda:0")
    model = PeftModel.from_pretrained(base, args.adapter)
    model.eval()
    model_vocab = base.get_input_embeddings().weight.shape[0]
    ti = xgr.TokenizerInfo.from_huggingface(tok, vocab_size=model_vocab,
                                            stop_token_ids=eos_ids)
    cg = xgr.GrammarCompiler(ti).compile_grammar(xgr.Grammar.from_ebnf(ebnf))
    return mode_generate(args, tok, base, model, lambda: xgr.GrammarMatcher(cg),
                         eos_ids, model_vocab)


if __name__ == "__main__":
    raise SystemExit(main())
