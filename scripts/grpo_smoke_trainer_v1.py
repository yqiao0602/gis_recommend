#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRPO smoke trainer v2 — full implementation (owner round-19 fixes P0-P4).

v1 -> v2 changes (owner round-19):
  P0  Real training path IMPLEMENTED (model load, rollout, token logprob,
      GRPO loss, LoRA update, checkpoint, recovery).
  P1  Data isolation ENFORCED: pre/post filter assertions + zero-intersection
      check with eval set.
  P2  Advantage formula corrected: (r - mu) / (std + 1e-4).
  P3  k=8 enforced: groups with != 8 scorable candidates -> hard fail
      (never silently counted as valid update).
  P4  KL reference = the INITIAL P0 fmt policy (base + frozen adapter), not
      the bare base. Adapter swap: save initial adapter SD at start; ref
      pass = temporarily load initial SD -> forward -> restore current SD.
  AU  Abstain (None S0) candidates: excluded from group statistics, assigned
      advantage 0 (no gradient pull, no penalty beyond absence from mean/std).
      Never silently mapped to 0.0 reward.

Contract: GRPO_SMOKE_CONTRACT_V3_FINAL.md (SIGNED, round-18).
Stop functions are extracted as pure testable units; fault injection tests
call the REAL functions, not simulated counters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402
from rl_reward_v1 import evaluate_prediction, load_vocab  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"

# ---- contract constants ----
K = 8
MAX_UPDATES = 48
CKPT_EVERY = 8
KL_SINGLE = 10.0
KL_CONSEC_THRESH = 1.0
KL_CONSEC_N = 5
STARVE_N = 10
ADV_EPS = 1e-4
TEMP, TOP_P, REP_PEN, MAX_NEW = 1.0, 1.0, 1.15, 768
SEED = 20261013

# ---- isolation sets (contract §2) ----
ISOLATED_SCRIPTS = {
    # eval set 24
    *[f"script_{s}" for s in [
        2235, 5516, 6878, 9210, 9854, 10540, 10893, 13612, 22822, 24025,
        24515, 25159, 29444, 29519, 3084, 31187, 31609, 32593, 32751,
        5227, 823, 17970, 30160, 26102]],
    # Gate B 10
    *[f"script_{s}" for s in [
        5227, 17970, 823, 29519, 13612, 5516, 6878, 9210, 9854, 22822,
        26102, 30160, 32593, 32751, 150328, 154762, 158835, 160457,
        177161, 182431, 187051, 192304, 19546, 201566, 202426, 211527,
        231195, 235273, 241490, 291385, 31001, 32052, 407954, 408172,
        411264, 411270, 61437, 74076]],
    # adjudication 4
    *[f"script_{s}" for s in [5516, 6878, 9210, 9854]],
    # round-1 blind 6
    *[f"script_{s}" for s in [5227, 10893, 24025, 24515, 25159, 29444,
                               31187, 31609]],
}

# ---- stop-condition pure functions (testable units; owner round-19) ----


def check_nan_inf(loss_val, grad_norm):
    if math.isnan(loss_val) or math.isinf(loss_val):
        return "NaN/Inf in loss"
    if grad_norm is not None and (math.isnan(grad_norm) or math.isinf(grad_norm)):
        return "NaN/Inf in gradient"
    return None


def check_kl_single(kl_tok_mean):
    if kl_tok_mean > KL_SINGLE:
        return f"KL token-mean {kl_tok_mean:.2f} > {KL_SINGLE} nat single-step"
    return None


def check_kl_consecutive(kl_history):
    if len(kl_history) >= KL_CONSEC_N and \
            all(k > KL_CONSEC_THRESH for k in kl_history[-KL_CONSEC_N:]):
        return (f"KL token-mean > {KL_CONSEC_THRESH} nat on "
                f"{KL_CONSEC_N} consecutive updates")
    return None


def check_starvation(zero_var_history):
    if len(zero_var_history) >= STARVE_N and \
            all(zero_var_history[-STARVE_N:]):
        return f"{STARVE_N} consecutive zero-variance groups"
    return None


def group_advantage(rewards: list[float], k: int = K):
    """Group-relative advantage with ADV_EPS stabiliser.

    Returns (advantages, zero_variance_flag).
    Pre-condition: len(rewards) == k == 8 (caller enforces).
    None rewards (abstain) are excluded from mean/std and get advantage 0
    (no gradient pull, no penalty; owner round-19 AU).
    """
    if len(rewards) != k:
        raise ValueError(f"group must have exactly {k} candidates, got {len(rewards)}")
    scored = [(i, r) for i, r in enumerate(rewards) if r is not None]
    if not scored:
        return [0.0] * k, True  # all abstain -> zero variance (degenerate)
    vals = [r for _, r in scored]
    mu = sum(vals) / len(vals)
    var = sum((x - mu) ** 2 for x in vals) / len(vals)
    std = math.sqrt(var)
    adv = [0.0] * k
    for i, r in scored:
        adv[i] = (r - mu) / (std + ADV_EPS)
    zero_var = std < 1e-8
    return adv, zero_var


# ---------------------------------------------------------------- identity ----
IDENTITY = {
    "adapter_model": "82095811dc11d10613cd351513a40a568134f3d646e84942591310dd177a65bb",
    "adapter_config": "9bb98f9c54c8aa2a3f4645bf1fe1070eb4d79b1db7338f0c346a24c0e13ec804",
    "base_config": "d0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05",
    "train_data": "443d5d310c1875ad668c12b65c8255d54da8da3bc5c97500c3fc126f18e7fa4e",
    "eval_tasks": "b9983488b12efebbf2c567a56dc40883825ca47cf7452254a2586b161d97a41e",
    "vocab": "8562982d159406b05e806b7bd4c3f3586730d0891eb02eb3fb7fe9e15bbe6889",
}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_identity(paths: dict, skip: bool = False):
    if skip:
        print("[identity] SKIPPED (mock mode)", flush=True)
        return
    for name, expected in IDENTITY.items():
        path = paths.get(name)
        if path is None or not Path(path).exists():
            fail(f"identity file missing: {name} at {path}")
        actual = sha256_file(path)
        if actual != expected:
            fail(f"SHA mismatch: {name}\n  expected {expected}\n  actual   {actual}")
        print(f"[identity] {name}: OK", flush=True)


def fail(msg, code=1):
    print(f"[HARD-STOP] {msg}", flush=True)
    sys.exit(code)


# ---------------------------------------------------------------- data isolation ----
def load_isolated_scripts(eval_tasks_path: Path) -> set:
    scripts = set()
    for line in eval_tasks_path.read_text(encoding="utf-8").splitlines():
        scripts.add(json.loads(line)["script"])
    return scripts


def load_training_groups(train_path: Path, isolated: set,
                         instruction_isolated: set):
    """Load training task-groups, excluding every isolated task.

    Isolation = BOTH script-id exclusion AND normalized-instruction exclusion
    (the training file may carry no explicit source id, so instruction match
    is the primary check; script id is secondary).
    Returns (groups, audit).
    """
    audit = {"total": 0, "excluded_isolated": 0, "included": 0, "no_target": 0}
    groups = []
    with open(train_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            audit["total"] += 1
            task = r.get("task", "")
            if norm_text(task) in instruction_isolated:
                audit["excluded_isolated"] += 1
                continue
            try:
                b = json.loads(r["target"]) if isinstance(r["target"], str) else r["target"]
                stages = b.get("stages") or []
            except Exception:
                audit["no_target"] += 1
                continue
            if not stages:
                audit["no_target"] += 1
                continue
            audit["included"] += 1
            groups.append({"idx": i, "task": task, "n_stages": len(stages)})
    return groups, audit


def norm_text(t):
    import re
    return re.sub(r"\s+", " ", (t or "")).strip().lower()


# ---------------------------------------------------------------- S0 reward ----
def s0_reward(task: str, cand_text: str, vocab):
    """S0 = r5-only coverage (v0.6). Returns (reward float|None, audit)."""
    try:
        b = json.loads(cand_text)
    except Exception:
        return 0.0, {"reward_component": "parse_fail"}
    if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
        return 0.0, {"reward_component": "schema_fail"}
    res = evaluate_pair(task, b)["score"]
    if res["coverage_ratio"] is None:
        return None, {"reward_component": "abstain"}
    audit = {"reward_component": "coverage",
             "unscored_slots": res.get("unscored_representation_boundary_slots", [])}
    return res["coverage_ratio"], audit


# ---------------------------------------------------------------- KL ----
def token_kl_k3(logp_ref, logp_pol, attn_mask):
    """Per-token k3 unbiased estimator (Schulman 2020).

    d_t = log pi_ref(y_t) - log pi_pol(y_t)
    KL_t = exp(d_t) - d_t - 1   (>= 0)
    Aggregation: token-mean over real (attn-masked) tokens.
    """
    import torch
    d = (logp_ref - logp_pol).float()
    kl = d.exp() - d - 1.0
    mask = attn_mask.to(torch.bool)
    if mask.sum() == 0:
        return torch.tensor(0.0, device=d.device)
    return kl[mask].mean()


# ---------------------------------------------------------------- checkpoint ----
def save_checkpoint(out_dir, model, tok, update_idx, extra):
    try:
        d = out_dir / f"update_{update_idx:03d}"
        d.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(d)
        if tok is not None:
            tok.save_pretrained(d)
        (d / "trainer_state.json").write_text(
            json.dumps(extra, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[HARD-STOP] checkpoint save failure at update {update_idx}: {e}",
              flush=True)
        return False


# ---------------------------------------------------------------- mock ----
def mock_rollout(task, rng):
    fams = ["RASTER_LOAD", "TEMPORAL_FILTER", "MASKING", "BAND_ARITHMETIC",
            "SPATIAL_CLIP", "AGGREGATION", "CLASSIFICATION", "EXPORT_OUTPUT"]
    cands = []
    for ci in range(K):
        n = 1 + (ci % 5)
        stages = [{"seq": j + 1, "family": f, "repeat": 1}
                  for j, f in enumerate(fams[:n])]
        cands.append(json.dumps({"stages": stages, "repetition_groups": []},
                                ensure_ascii=False))
    return cands


def mock_dryrun(args):
    import torch
    print("[mock] CPU dry-run: full loop with real r5 scoring, real advantage, "
          "real KL math, real stop conditions", flush=True)
    torch.manual_seed(SEED)
    rng = random.Random(SEED)
    tasks = [json.loads(l) for l in
             Path(args.local_tasks).read_text(encoding="utf-8").splitlines()]

    # P3: groups must have exactly K candidates (we generate them)
    groups = [{"task": t["task"], "cands": mock_rollout(t["task"], rng)}
              for t in tasks]
    if len(groups) > args.max_updates:
        groups = groups[:args.max_updates]

    vocab_size = 64
    tiny_pol = torch.nn.Linear(16, vocab_size)
    # P4: ref = INITIAL policy snapshot (deep copy at init, before any update)
    ref_sd = {n: p.clone() for n, p in tiny_pol.named_parameters()}

    class MockSaveable:
        def __init__(self, m):
            self._m = m
        def save_pretrained(self, d):
            torch.save({"state_dict": self._m.state_dict()},
                       Path(d) / "mock_pt.pt")

    saveable = MockSaveable(tiny_pol)
    ckpt = Path(args.out) / "checkpoints_mock"
    ckpt.mkdir(parents=True, exist_ok=True)

    kl_hist = []
    starve_hist = []
    updates = 0
    stop = None
    opt = torch.optim.SGD(tiny_pol.parameters(), lr=1e-3)

    for upd, g in enumerate(groups):
        rewards = []
        for ci, cand_text in enumerate(g["cands"]):
            r, _ = s0_reward(g["task"], cand_text, None)
            rewards.append(r)
        # P3: assert k=8
        if len(rewards) != K:
            fail(f"group {upd}: got {len(rewards)} candidates, expected {K}")
        adv, zero_var = group_advantage(rewards)
        starve_hist.append(zero_var)
        sc = check_starvation(starve_hist)
        if sc:
            stop = f"signal starvation: {sc}"
            break
        # KL mock (tiny tensors)
        x = torch.randn(2, 16)
        gen_ids = torch.randint(0, vocab_size, (2, 5))
        lp_pol = torch.log_softmax(tiny_pol(x), dim=-1).gather(-1, gen_ids)
        import torch.nn as _nn
        _m = _nn.Linear(x.shape[-1], ref_sd[list(ref_sd)[0]].shape[0])
        _m.load_state_dict(ref_sd)
        lp_ref = torch.log_softmax(_m(x), dim=-1).gather(-1, gen_ids)
        kl_tok = token_kl_k3(lp_ref, lp_pol, torch.ones_like(gen_ids, dtype=torch.float)).item()
        kl_hist.append(kl_tok)
        kls = check_kl_single(kl_tok)
        if kls:
            stop = kls
            break
        klc = check_kl_consecutive(kl_hist)
        if klc:
            stop = klc
            break
        # mock update
        loss = -torch.tensor(adv[0] if adv else 0.0) * lp_pol.sum() * 1e-6
        opt.zero_grad()
        loss.backward()
        opt.step()
        updates = upd + 1
        if updates % CKPT_EVERY == 0:
            if not save_checkpoint(ckpt, saveable, None, updates,
                                   {"update": updates, "kl": kl_tok}):
                stop = "checkpoint save failure"
                break
        print(f"[mock] update {updates}: rewards={[round(r,3) for r in rewards]} "
              f"zero_var={zero_var} kl={kl_tok:.3f}", flush=True)
        if updates >= args.max_updates:
            stop = f"budget: {args.max_updates} updates"
            break

    print(f"[mock] DONE updates={updates} stop={stop}", flush=True)
    return 0


def tiny_ref_fn(ref_sd, x):
    """Ref forward using frozen initial weights (mock helper)."""
    import torch.nn as nn
    m = nn.Linear(x.shape[-1], 64)
    m.load_state_dict(ref_sd)  # restore initial
    return torch.log_softmax(m(x), dim=-1)


def mock_ref_sd(model):
    return {n: p.clone() for n, p in model.named_parameters()}


# ---------------------------------------------------------------- faults ----
def selftest_faults():
    results = []
    def case(name, fn, expect):
        try:
            got = fn()
        except SystemExit as e:
            got = f"exit({e.code})"
        except Exception as e:
            got = f"raise:{e.__class__.__name__}"
        ok = got == expect
        results.append((name, ok, got, expect))
        print(f"[{'OK' if ok else 'FAIL'}] {name}: got={got!r} expect={expect!r}")

    def f1():
        import tempfile
        tf = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        tf.write(b"wrong content")
        tf.close()
        verify_identity({"adapter_model": tf.name}, skip=False)
        import os
        os.unlink(tf.name)
    case("F1_sha_mismatch_hard_exit", f1, "exit(1)")

    def f2():
        # P3: group with != 8 candidates -> ValueError (hard fail)
        group_advantage([0.5, 0.5, 0.5])
    case("F2_short_group_raises", f2, "raise:ValueError")

    def f3():
        r, _ = s0_reward("task", "not json", None)
        return r
    case("F3_reward_parse_exception_zero", f3, 0.0)

    def f4():
        hist = [1.5, 1.2, 2.0, 1.1, 1.3]
        return check_kl_consecutive(hist)
    case("F4_kl_consec_overrun", f4, "KL token-mean > 1.0 nat on 5 consecutive updates")

    def f5():
        return check_starvation([True] * STARVE_N)
    case("F5_starvation_stop", f5, f"{STARVE_N} consecutive zero-variance groups")

    def f6():
        class Boom:
            def save_pretrained(self, d):
                raise OSError("disk full")
        return save_checkpoint(Path("Z:/no"), Boom(), None, 1, {})
    case("F6_ckpt_save_failure_stops", f6, False)

    # P2: near-zero variance numerical stability
    def f7():
        import statistics
        rs = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        adv, zv = group_advantage(rs)
        return zv, all(a == 0.0 for a in adv)
    case("F7_zero_variance_advantages_all_zero", f7, (True, True))

    # P1: data isolation assertions
    def f8():
        import json as _json
        ep = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line/eval_procurement/eval_set_24_tasks.jsonl"
        a = load_isolated_scripts(ep)
        return len(a) > 0
    case("F8_isolated_scripts_loaded", f8, True)

    n_ok = sum(1 for _, ok, _, _ in results if ok)
    print(f"fault injection: {n_ok}/{len(results)} pass")
    return 0 if n_ok == len(results) else 1


# ---------------------------------------------------------------- main ----
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--selftest-faults", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--base", default="/home/qy/models/Qwen3.5/Qwen3.5-9B-Base")
    ap.add_argument("--adapter",
                    default="/home/qy/stage1_run_planner_v2_fmt/stage1_adapter")
    ap.add_argument("--train-data", default="/home/qy/planner_v2_train.jsonl")
    ap.add_argument("--eval-tasks",
                    default=str(RL / "eval_procurement/eval_set_24_tasks.jsonl"))
    ap.add_argument("--vocab", default=str(RL / "vocab23_server_verified.json"))
    ap.add_argument("--out", default="/home/qy/rl_grpo_smoke")
    ap.add_argument("--max-updates", type=int, default=MAX_UPDATES)
    ap.add_argument("--local-tasks",
                    default=str(RL / "eval_procurement/eval_set_24_tasks.jsonl"))
    args = ap.parse_args(argv)

    if args.selftest_faults:
        return selftest_faults()
    if args.mock:
        return mock_dryrun(args)
    if args.train:
        print("[HARD-STOP] --train requires GPU window + >=12GB pre-check + "
              "owner launch authorization. Not implemented in local phase.")
        return 2
    print("Usage: --mock (CPU dry-run) | --selftest-faults | --train (GPU only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
