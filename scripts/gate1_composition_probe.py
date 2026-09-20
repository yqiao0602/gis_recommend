#!/usr/bin/env python3
"""Gate 1: GEE composition learnability probe (frozen spec ea8862a).

From-scratch ~3.4M decoder trained on gee_canonical_chain op sequences;
chain-disjoint held-out next-op evaluation against pre-registered frequency
baselines. Read-only corpus, CPU-only (no route2 GPU contention).

Design fixed by spec (docs/plans/transfer_phase2_gate1_spec.md):
  4L / d256 / 8 heads / dff1024 / ctx 256 ops / dropout 0.1 / tied embedding
  AdamW lr 3e-4 wd 0.01 cosine->10% warmup (revised 500->100 at smoke stage,
  spec 6.3 single documented revision) / <=8 epochs early-stop patience 2
  seeds 20260920/21/22, verdict on the mean.

Owner additions 2026-09-20 (report-only, criteria unchanged): effect size
+ bootstrap 95% CI, length buckets 8-11/12-15/16-31/32+ as diagnostics,
fixed report table.

Two-phase discipline (Gate 0 errata lesson): the corpus is row-shuffled, so
every train-membership test runs only after the complete train set is built.
"""
import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

PAD, UNK, BOS, EOS = 0, 1, 2, 3
OPS_CAP = 256                      # ops kept per chain (spec: ctx 256, p99=246)
MAX_LEN = OPS_CAP + 2              # BOS + ops + EOS
SPECIALS = 4
BUCKETS = [(2, 7), (8, 11), (12, 15), (16, 31), (32, 10 ** 9)]
BUCKET_NAMES = ["2-7", "8-11", "12-15", "16-31", "32+"]

# Independent anchor implementation (server 2026-09-20, same truncated
# universe) for smoke check 2; official baselines are always recomputed
# at runtime on identical positions (spec section 2).
ANCHORS_TRUNCATED = {
    "b0.d": 0.0581, "b1.d": 0.2685, "b2.d": 0.3969,
    "b0.ld": 0.0577, "b1.ld": 0.2691, "b2.ld": 0.4017,
}


def bucket_of(n):
    for (lo, hi), name in zip(BUCKETS, BUCKET_NAMES):
        if lo <= n <= hi:
            return BUCKET_NAMES.index(name)
    return len(BUCKET_NAMES) - 1


def load_corpus(path):
    """Two surfaces from the frozen file: train op-id lists and buffered
    eval rows; sha256 accumulated over raw bytes."""
    train_raw, eval_rows = [], []          # op-string lists
    train_keys = set()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for raw in f:
            h.update(raw)
            r = json.loads(raw.decode("utf-8"))
            # OPS_CAP truncation up front so that membership, baseline tables
            # and eval positions all share the truncated universe (matches
            # the independent anchor computation; spec section 2)
            ch = [x.strip() for x in
                  r.get("gee_canonical_chain", "").split("->") if x.strip()][:OPS_CAP]
            sp = r.get("split")
            if sp == "train":
                train_raw.append(ch)
                train_keys.add(tuple(ch))
            elif sp in ("val", "test"):
                # buffered: membership tested later against the COMPLETE
                # train set (file is row-shuffled; single-pass undercounted)
                eval_rows.append((sp, tuple(ch)))
    return train_raw, eval_rows, train_keys, h.hexdigest()


def build_vocab(train_raw):
    ops = sorted({o for ch in train_raw for o in ch})
    op2id = {o: SPECIALS + i for i, o in enumerate(ops)}
    return op2id, len(ops) + SPECIALS


class Baselines:
    """B0/B1/B2 frequency tables in id space, fit on train only."""

    def fit(self, train_id_lists):
        uni, bi, tri = Counter(), Counter(), Counter()
        for c in train_id_lists:
            uni.update(c)
            bi.update(zip(c, c[1:]))
            tri.update(zip(c, c[1:], c[2:]))
        self.b0 = uni.most_common(1)[0][0]
        self.bi_best, self.tri_best = {}, {}
        for (a, b), n in bi.items():
            if a not in self.bi_best or n > self.bi_best[a][1]:
                self.bi_best[a] = (b, n)
        for (a, b, c), n in tri.items():
            if (a, b) not in self.tri_best or n > self.tri_best[(a, b)][1]:
                self.tri_best[(a, b)] = (c, n)
        return self

    def preds(self, t):
        """Per gate position i (1..L-1): (b0, b1, b2) predictions."""
        out = []
        for i in range(1, len(t)):
            b1 = self.bi_best.get(t[i - 1], (self.b0, 0))[0]
            b2 = self.tri_best.get((t[i - 2], t[i - 1]), (b1, 0))[0] \
                if i >= 2 else b1
            out.append((self.b0, b1, b2))
        return out


class Block(nn.Module):
    def __init__(self, d, heads, ff, drop):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.h = heads
        self.dk = d // heads
        self.q = nn.Linear(d, d)
        self.k = nn.Linear(d, d)
        self.v = nn.Linear(d, d)
        self.proj = nn.Linear(d, d)
        self.ff = nn.Sequential(nn.Linear(d, ff), nn.GELU(),
                                nn.Linear(ff, d), nn.Dropout(drop))
        self.drop = nn.Dropout(drop)

    def forward(self, x, mask):
        B, T, D = x.shape
        q = self.q(self.ln1(x)).view(B, T, self.h, self.dk).transpose(1, 2)
        k = self.k(self.ln1(x)).view(B, T, self.h, self.dk).transpose(1, 2)
        v = self.v(self.ln1(x)).view(B, T, self.h, self.dk).transpose(1, 2)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.dk)
        att = att.masked_fill(mask, float("-inf")).softmax(dim=-1)
        y = self.drop((att @ v).transpose(1, 2).contiguous().view(B, T, D))
        x = x + self.proj(y)
        x = x + self.ff(self.ln2(x))
        return x


class Probe(nn.Module):
    def __init__(self, vocab, d=256, layers=4, heads=8, ff=1024, drop=0.1):
        super().__init__()
        self.emb = nn.Embedding(vocab, d)
        self.pos = nn.Embedding(MAX_LEN, d)
        self.inp = nn.Dropout(drop)
        self.blocks = nn.ModuleList(Block(d, heads, ff, drop)
                                    for _ in range(layers))
        self.ln_f = nn.LayerNorm(d)
        self.head = nn.Linear(d, vocab, bias=False)
        self.head.weight = self.emb.weight          # tied

    def forward(self, idx):
        B, T = idx.shape
        mask = torch.triu(torch.ones(T, T, dtype=torch.bool,
                                     device=idx.device), diagonal=1)
        x = self.inp(self.emb(idx) + self.pos(torch.arange(T,
                         device=idx.device)))
        for blk in self.blocks:
            x = blk(x, mask)
        return self.head(self.ln_f(x))


def seq_of(op_ids):
    return [BOS] + list(op_ids) + [EOS]


def gate_positions(op_ids):
    """Seq positions p of gold tokens t_1..t_{L-1} (BOS at 0, t_0 at 1)."""
    return list(range(2, len(op_ids) + 1))


def make_batches(id_lists, budget, rng=None):
    order = np.arange(len(id_lists))
    if rng is not None:
        rng.shuffle(order)
    batch, tokens = [], 0
    for i in order:
        s = seq_of(id_lists[i])
        if batch and tokens + len(s) > budget:
            yield batch
            batch, tokens = [], 0
        batch.append(s)
        tokens += len(s)
    if batch:
        yield batch


def pad_batch(seqs):
    T = max(len(s) for s in seqs)
    x = torch.full((len(seqs), T), PAD, dtype=torch.long)
    for i, s in enumerate(seqs):
        x[i, :len(s)] = torch.tensor(s, dtype=torch.long)
    return x


def lr_scale(step, warmup, total):
    if step < warmup:
        return (step + 1) / warmup
    frac = (step - warmup) / max(total - warmup, 1)
    return 0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(frac, 1.0)))


@torch.no_grad()
def eval_model(model, id_lists, flat_n, pos_chains, pos_slots, bs=48):
    """top1/top3 correctness arrays in flat position order."""
    top1 = np.zeros(flat_n, dtype=np.int8)
    top3 = np.zeros(flat_n, dtype=np.int8)
    model.eval()
    for s in range(0, len(id_lists), bs):
        chunk = id_lists[s:s + bs]
        x = pad_batch([seq_of(c) for c in chunk])
        logits = model(x)[:, :-1]
        best = logits.topk(3, dim=-1).indices          # (B, T-1, 3)
        for bi, c in enumerate(chunk):
            for p in gate_positions(c):
                slot = pos_slots[(s + bi, p)]
                gold = c[p - 2 + 1]                    # seq pos p holds gold
                idxs = best[bi, p - 1]
                top1[slot] = int(idxs[0].item() == gold)
                top3[slot] = int(gold in idxs.tolist())
    model.train()
    return top1, top3


def eval_baselines(base, id_lists, flat_n, pos_slots):
    b0 = np.zeros(flat_n, dtype=np.int8)
    b1 = np.zeros(flat_n, dtype=np.int8)
    b2 = np.zeros(flat_n, dtype=np.int8)
    for ci, c in enumerate(id_lists):
        for p, (p0, p1, p2) in zip(gate_positions(c), base.preds(c)):
            slot = pos_slots[(ci, p)]
            gold = c[p - 2 + 1]
            b0[slot] = int(p0 == gold)
            b1[slot] = int(p1 == gold)
            b2[slot] = int(p2 == gold)
    return b0, b1, b2


def position_index(id_lists):
    """Flat position order shared by every evaluator; plus bucket labels."""
    pos_chains, pos_slots, buckets = [], {}, []
    for ci, c in enumerate(id_lists):
        for p in gate_positions(c):
            pos_slots[(ci, p)] = len(pos_chains)
            pos_chains.append((ci, p))
            buckets.append(bucket_of(len(c)))
    return pos_chains, pos_slots, np.array(buckets, dtype=np.int8)


def mask_of_buckets(buckets_arr, sel):
    return buckets_arr == sel


def bootstrap_delta(a, b, iters=1000, seed=0):
    """95% percentile CI of mean(a-b) over position resamples."""
    rng = np.random.default_rng(seed)
    d = a.astype(np.float64) - b.astype(np.float64)
    n = len(d)
    means = np.empty(iters)
    for i in range(iters):
        idx = rng.integers(0, n, n)
        means[i] = d[idx].mean()
    return [round(float(np.percentile(means, 2.5)), 4),
            round(float(np.percentile(means, 97.5)), 4)]


@torch.no_grad()
def generation_diag(model, id_lists, n=500, seed=0):
    """Greedy full-chain generation on the first n disjoint-test rows;
    op-set multiset F1 vs full gold + length ratio (diagnostic only)."""
    model.eval()
    f1s, ratios = [], []
    for s in range(0, min(n, len(id_lists)), 50):
        chunk = id_lists[s:s + 50]
        x = pad_batch([[BOS] for _ in chunk])          # width 1
        done = np.zeros(len(chunk), dtype=bool)
        for _ in range(OPS_CAP):
            nxt = model(x)[:, -1].argmax(-1)
            # grow first, then write: overwriting the last column would
            # corrupt the generated history (caught in self-review)
            x = torch.cat([x, torch.full((len(chunk), 1), PAD,
                                         dtype=torch.long)], dim=1)
            for bi in range(len(chunk)):
                if done[bi]:
                    continue
                t = int(nxt[bi])
                x[bi, -1] = t
                if t == EOS or x.shape[1] >= MAX_LEN:
                    done[bi] = True
            if done.all():
                break
        for bi, c in enumerate(chunk):
            gen = [t for t in x[bi].tolist()
                   if t not in (PAD, BOS, EOS)]
            gold = list(c)
            inter = sum((Counter(gen) & Counter(gold)).values())
            f1 = 2 * inter / max(len(gen) + len(gold), 1)
            f1s.append(f1)
            ratios.append(len(gen) / max(len(gold), 1))
    model.train()
    return {"op_set_f1_mean": round(float(np.mean(f1s)), 4),
            "length_ratio_mean": round(float(np.mean(ratios)), 4),
            "n_rows": len(f1s)}


def run_smoke(args):
    t0 = time.time()
    print("[smoke] loading full corpus for baseline pipeline check...", flush=True)
    train_raw, eval_rows, train_keys, sha = load_corpus(args.corpus)
    op2id, vocab = build_vocab(train_raw)
    train_ids = [[op2id[o] for o in ch] for ch in train_raw]
    enc = lambda t: [op2id.get(o, UNK) for o in t]
    val_disc = [enc(list(t)) for sp, t in eval_rows
                if sp == "val" and t not in train_keys and len(t) >= 2]
    test_disc = [enc(list(t)) for sp, t in eval_rows
                 if sp == "test" and t not in train_keys and len(t) >= 2]
    base = Baselines().fit(train_ids)

    # check 2: independent anchors, same truncated universe (±0.3pp)
    pc, ps, _ = position_index(test_disc)
    long_m = np.array([bucket_of(len(c)) >= BUCKET_NAMES.index("12-15")
                       for c in test_disc for _ in gate_positions(c)])
    b0, b1, b2 = eval_baselines(base, test_disc, len(pc), ps)
    got = {"b0.d": b0.mean(), "b1.d": b1.mean(), "b2.d": b2.mean(),
           "b0.ld": b0[long_m].mean(), "b1.ld": b1[long_m].mean(),
           "b2.ld": b2[long_m].mean()}
    ok2 = True
    print("[smoke] baseline pipeline check vs independent anchors:", flush=True)
    for k, v in got.items():
        diff = abs(v - ANCHORS_TRUNCATED[k])
        ok = diff <= 0.003
        ok2 &= ok
        print("  %s got=%.4f anchor=%.4f diff=%.4f %s"
              % (k, v, ANCHORS_TRUNCATED[k], diff, "OK" if ok else "FAIL"),
              flush=True)

    # checks 1+3: 2k-row self-contained universe, 2,000 steps
    sub_raw = train_raw[:2000]
    sop2id, svocab = build_vocab(sub_raw)
    sids = [[sop2id[o] for o in ch] for ch in sub_raw]
    sbase = Baselines().fit(sids)
    spc, sps, sbk = position_index(sids)
    sb0, sb1, sb2 = eval_baselines(sbase, sids, len(spc), sps)
    torch.manual_seed(args.seed)
    model = Probe(svocab)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    rng = np.random.default_rng(args.seed)
    model.train()
    losses = []
    step = 0
    for epoch in range(20):
        if step >= args.smoke_steps:
            break
        for batch in make_batches(sids, args.smoke_budget, rng):
            if step >= args.smoke_steps:
                break
            x = pad_batch(batch)
            logits = model(x)
            loss = F.cross_entropy(logits[:, :-1].reshape(-1, svocab),
                                   x[:, 1:].reshape(-1),
                                   ignore_index=PAD)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss))
            step += 1
            if step % 250 == 0:
                print("[smoke] step %d loss %.3f" % (step, loss), flush=True)
    tail = float(np.mean(losses[-100:]))
    ok1 = tail < 4.0
    print("[smoke] check1 train loss (last-100 mean) = %.3f  threshold 4.0  %s"
          % (tail, "OK" if ok1 else "FAIL"), flush=True)
    mtop1, _ = eval_model(model, sids, len(spc), sps)
    ok3 = mtop1.mean() >= sb2.mean()
    print("[smoke] check3 capacity: model %.4f vs B2 %.4f on same positions  %s"
          % (mtop1.mean(), sb2.mean(), "OK" if ok3 else "FAIL"), flush=True)
    print("[smoke] SMOKE %s in %.1f min (warmup revision 500->100 documented "
          "per spec 6.3)" % ("PASS" if (ok1 and ok2 and ok3) else "FAIL",
                             (time.time() - t0) / 60), flush=True)
    return 0 if (ok1 and ok2 and ok3) else 1


def run_seed(args):
    t0 = time.time()
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    train_raw, eval_rows, train_keys, sha = load_corpus(args.corpus)
    op2id, vocab = build_vocab(train_raw)
    train_ids = [[op2id[o] for o in ch] for ch in train_raw]
    enc = lambda t: [op2id.get(o, UNK) for o in t]
    val_disc = [enc(list(t)) for sp, t in eval_rows
                if sp == "val" and t not in train_keys and len(t) >= 2]
    test_disc = [enc(list(t)) for sp, t in eval_rows
                 if sp == "test" and t not in train_keys and len(t) >= 2]
    test_full = [enc(list(t)) for sp, t in eval_rows
                 if sp == "test" and len(t) >= 2]
    n_unk = sum(1 for c in test_disc for o in c if o == UNK)
    total_train_tokens = sum(len(c) for c in train_ids)
    est_steps = int(args.max_epochs * total_train_tokens / args.budget)
    print("[seed %d] train %d rows / %d tokens, vocab %d, val_disc %d, "
          "test_disc %d (unk-gold positions %d), est_steps %d"
          % (args.seed, len(train_ids), total_train_tokens, vocab,
             len(val_disc), len(test_disc), n_unk, est_steps), flush=True)

    model = Probe(vocab)
    print("[seed %d] params %.2fM" % (args.seed,
          sum(p.numel() for p in model.parameters()) / 1e6), flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    # model selection: disjoint-val next-op top-1 (spec section 3)
    vpc, vps, vbk = position_index(val_disc)
    best_val, best_epoch, best_state, bad = -1.0, 0, None, 0
    step = 0
    model.train()
    for epoch in range(1, args.max_epochs + 1):
        ep_loss, ep_n = [], 0
        te = time.time()
        for batch in make_batches(train_ids, args.budget, rng):
            x = pad_batch(batch)
            logits = model(x)
            loss = F.cross_entropy(logits[:, :-1].reshape(-1, vocab),
                                   x[:, 1:].reshape(-1), ignore_index=PAD)
            for g, p in zip(opt.param_groups, [args.lr * lr_scale(
                    step, args.warmup, est_steps)]):
                g["lr"] = p
            opt.zero_grad()
            loss.backward()
            opt.step()
            step += 1
            ep_loss.append(float(loss))
            ep_n += 1
            if ep_n % 50 == 0:
                print("[seed %d] ep%d step %d loss %.3f lr %.2e (%.1fs)"
                      % (args.seed, epoch, step, loss,
                         opt.param_groups[0]["lr"], time.time() - te),
                      flush=True)
        vt1, _ = eval_model(model, val_disc, len(vpc), vps)
        v = float(vt1.mean())
        print("[seed %d] epoch %d done: loss %.3f val_disc_top1 %.4f (%.1f min)"
              % (args.seed, epoch, np.mean(ep_loss), v,
                 (time.time() - te) / 60), flush=True)
        if v > best_val:
            best_val, best_epoch, bad = v, epoch, 0
            best_state = {k: t.clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= 2:
                print("[seed %d] early stop (patience 2) at epoch %d"
                      % (args.seed, epoch), flush=True)
                break
    model.load_state_dict(best_state)

    # official evaluation: identical positions for model and baselines
    tpc, tps, tbk = position_index(test_disc)
    long_m = np.array([bucket_of(len(c)) >= BUCKET_NAMES.index("12-15")
                       for c in test_disc for _ in gate_positions(c)])
    mt1, mt3 = eval_model(model, test_disc, len(tpc), tps)
    b0a, b1a, b2a = eval_baselines(Baselines().fit(train_ids), test_disc,
                                   len(tpc), tps)

    per_bucket = {}
    for bi, name in enumerate(BUCKET_NAMES):
        m = tbk == bi
        if m.any():
            per_bucket[name] = {
                "n": int(m.sum()),
                "model_top1": round(float(mt1[m].mean()), 4),
                "b2_top1": round(float(b2a[m].mean()), 4),
                "model_top3": round(float(mt3[m].mean()), 4)}

    # full-test dual report (secondary, contains leaked chains)
    fpc, fps, fbk = position_index(test_full)
    fmt1, _ = eval_model(model, test_full, len(fpc), fps)

    res = {
        "schema": "gis_recommend.transfer.gate1.seed", "seed": args.seed,
        "sha256": sha, "params_m": round(sum(p.numel() for p in
                                             model.parameters()) / 1e6, 3),
        "config": {"layers": 4, "d": 256, "heads": 8, "ff": 1024,
                   "ctx_ops": OPS_CAP, "dropout": 0.1, "lr": args.lr,
                   "wd": 0.01, "warmup": args.warmup,
                   "warmup_note": "revised 500->100 at smoke stage (spec 6.3)",
                   "max_epochs": args.max_epochs, "budget": args.budget,
                   "best_epoch": best_epoch, "best_val_disc_top1": round(
                       best_val, 4)},
        "baselines_official": {
            "b0_disjoint": round(float(b0a.mean()), 4),
            "b1_disjoint": round(float(b1a.mean()), 4),
            "b2_disjoint": round(float(b2a.mean()), 4),
            "b0_long": round(float(b0a[long_m].mean()), 4),
            "b1_long": round(float(b1a[long_m].mean()), 4),
            "b2_long": round(float(b2a[long_m].mean()), 4),
            "n_positions": int(len(tpc)), "n_long": int(long_m.sum()),
            "n_unk_gold_positions": n_unk},
        "model": {
            "disjoint_top1": round(float(mt1.mean()), 4),
            "disjoint_top3": round(float(mt3.mean()), 4),
            "long_top1": round(float(mt1[long_m].mean()), 4),
            "full_test_top1_secondary": round(float(fmt1.mean()), 4)},
        "delta_vs_b2": {
            "disjoint": round(float(mt1.mean() - b2a.mean()), 4),
            "disjoint_ci95": bootstrap_delta(mt1, b2a, seed=args.seed),
            "long": round(float(mt1[long_m].mean() - b2a[long_m].mean()), 4),
            "long_ci95": bootstrap_delta(mt1[long_m], b2a[long_m],
                                         seed=args.seed + 1)},
        "delta_vs_b1": {
            "disjoint": round(float(mt1.mean() - b1a.mean()), 4),
            "long": round(float(mt1[long_m].mean() - b1a[long_m].mean()), 4)},
        "length_buckets": per_bucket,
        "generation_diagnostic": generation_diag(model, test_disc, n=500),
        "minutes": round((time.time() - t0) / 60, 1),
    }
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("gate1_seed%d_metrics.json" % args.seed)
    path.write_text(json.dumps(res, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print("[seed %d] WROTE %s" % (args.seed, path), flush=True)
    print("[seed %d] GATE1 SEED DONE" % args.seed, flush=True)
    return 0


def run_aggregate(args):
    out = Path(args.out_dir)
    seeds = sorted(out.glob("gate1_seed*_metrics.json"))
    assert seeds, "no seed metrics found"
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in seeds]
    d_ = [r["model"]["disjoint_top1"] for r in rows]
    l_ = [r["model"]["long_top1"] for r in rows]
    b = rows[0]["baselines_official"]
    mean = lambda v: float(np.mean(v))
    sd = lambda v: float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
    m_d, m_l = mean(d_), mean(l_)
    verdict = ("PASS" if (m_d >= b["b2_disjoint"] + 0.05 and
                          m_l >= b["b2_long"] + 0.05)
               else "FAIL" if (m_d <= b["b1_disjoint"] + 0.05 or
                               m_l <= b["b1_long"] + 0.05)
               else "MIDDLE")
    summary = {
        "schema": "gis_recommend.transfer.gate1.summary",
        "n_seeds": len(rows),
        "seeds": [r["seed"] for r in rows],
        "baselines_official": b,
        "model_disjoint_top1": {"mean": round(m_d, 4), "sd": round(sd(d_), 4),
                                "values": d_},
        "model_long_top1": {"mean": round(m_l, 4), "sd": round(sd(l_), 4),
                            "values": l_},
        "delta_vs_b2_per_seed": {str(r["seed"]): r["delta_vs_b2"]
                                 for r in rows},
        "verdict": verdict,
    }
    (out / "gate1_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    ci_str = " | ".join(
        "s%d %s" % (r["seed"], r["delta_vs_b2"]["disjoint_ci95"])
        for r in rows)
    print("""
| 指标 | B0 | B1 | B2 | Transformer | Δ vs B2 |
|---|---:|---:|---:|---:|---:|
| Test Top-1 (disjoint) | %.2f | %.2f | **%.2f** | %.2f | %+.2f |
| Long >=12 Top-1 | %.2f | %.2f | **%.2f** | %.2f | %+.2f |
| Seed SD (top-1) | — | — | — | %.2f / %.2f | — |
| Δ 95%% CI per seed | — | — | — | %s | — |
| VERDICT | %s |""" % (
        100 * b["b0_disjoint"], 100 * b["b1_disjoint"],
        100 * b["b2_disjoint"], 100 * m_d, 100 * (m_d - b["b2_disjoint"]),
        100 * b["b0_long"], 100 * b["b1_long"], 100 * b["b2_long"],
        100 * m_l, 100 * (m_l - b["b2_long"]),
        100 * sd(d_), 100 * sd(l_), ci_str, verdict))
    print("GATE1 ALL DONE")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--mode", choices=["smoke", "seed", "aggregate"],
                    required=True)
    ap.add_argument("--seed", type=int, default=20260920)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--warmup", type=int, default=100)
    ap.add_argument("--max-epochs", type=int, default=8)
    ap.add_argument("--budget", type=int, default=16384)
    ap.add_argument("--smoke-steps", type=int, default=2000)
    ap.add_argument("--smoke-budget", type=int, default=2048)
    args = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("GATE1_THREADS", "0")) or
                          (os.cpu_count() or 4))
    return {"smoke": run_smoke, "seed": run_seed,
            "aggregate": run_aggregate}[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())
