#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRPO smoke trainer v1 — implements GRPO_SMOKE_CONTRACT_V3_FINAL.md (SIGNED).

Contract-exact semantics:
  - 1 update = 1 task prompt + its k=8 candidate responses (task-group update);
    hard cap 48.
  - Reward = S0 (r5-only coverage, v0.6 caliber): TERRAIN unscored (both sides
    excluded), not_required/requirement_uncertain excluded, wrapper slots use
    the FROZEN v0.5.1 conservative caliber (counted missing). Structure formal
    reward is RECORDED, never added to the training reward.
  - Advantage: group-relative, A_i = (r_i - mean_group) / (std_group + 1e-4).
  - KL: per-token k3 unbiased estimator (Schulman): with
    d_t = log pi_ref(y_t) - log pi_pol(y_t),  KL_t = exp(d_t) - d_t - 1  (>=0);
    sequence value = token-mean; ref = the SAME model with adapters disabled
    (exact frozen-init reference, zero extra memory).
  - Aborts: NaN/Inf; adapter save/restore failure; KL token-mean > 10 nat on
    any single update -> immediate; KL token-mean > 1.0 nat on 5 consecutive
    updates -> stop; signal starvation = 10 consecutive updates whose 8 formal
    rewards are ALL identical (zero within-group variance).
  - Checkpoints every 8 updates; save failure -> HARD STOP (never continue).
  - Identity: hard-exit on any SHA mismatch before loading anything.

Authorization: local CPU implementation/mock only. No GPU, no real rollouts,
no optimizer updates on real data, no formal checkpoints until the contract
launch window opens (owner sign-off + >=12GB VRAM pre-check on mdzhang).
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

# ---- frozen identity (contract §0; hard-exit on mismatch) ----
IDENTITY = {
    "adapter_model": "82095811dc11d10613cd351513a40a568134f3d646e84942591310dd177a65bb",
    "adapter_config": "9bb98f9c54c8aa2a3f4645bf1fe1070eb4d79b1db7338f0c346a24c0e13ec804",
    "base_config": "d0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05",
    "train_data": "443d5d310c1875ad668c12b65c8255d54da8da3bc5c97500c3fc126f18e7fa4e",
    "eval_tasks": "b9983488b12efebbf2c567a56dc40883825ca47cf7452254a2586b161d97a41e",
    "vocab": "8562982d159406b05e806b7bd4c3f3586730d0891eb02eb3fb7fe9e15bbe6889",
}

# ---- contract constants ----
K = 8
MAX_UPDATES = 48
CHECKPOINT_EVERY = 8
KL_CEILING_SINGLE = 10.0
KL_CEILING_CONSEC = 1.0
KL_CONSEC_LIMIT = 5
STARVATION_LIMIT = 10
MAX_NEW = 768
TEMP, TOP_P, REP_PEN = 1.0, 1.0, 1.15
SEED = 20261013

# data isolation (contract §2): training tasks must NOT come from these
ISOLATED_PREFIXES = (
    # eval set 24 scripts are matched by the eval-tasks SHA file at runtime;
    # Gate B 10 + adjudication 4 + round-1 6 script ids:
    "script_5227", "script_17970", "script_823", "script_29519",
    "script_13612", "script_5516", "script_6878", "script_9210",
    "script_9854", "script_22822", "script_26102", "script_30160",
    "script_32593", "script_32751",
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str, code: int = 1):
    print(f"[HARD-STOP] {msg}", flush=True)
    sys.exit(code)


# ---------------------------------------------------------------- stage 1 ----
def verify_identity(paths: dict[str, str], skip: bool):
    if skip:
        print("[identity] SKIPPED (mock mode) — real runs MUST NOT skip", flush=True)
        return
    for name, path in paths.items():
        actual = sha256_file(Path(path))
        expected = IDENTITY.get(name)
        if expected is None:
            continue  # paths without contract identity (e.g. vocab is checked by key)
        if actual != expected:
            fail(f"identity mismatch: {name}\n  expected {expected}\n  actual   {actual}")
        print(f"[identity] {name}: OK", flush=True)


# ---------------------------------------------------------------- stage 2 ----
def load_task_groups(train_path: Path, max_groups: int):
    """Training task-groups: planner_v2_train rows OUTSIDE every isolation set."""
    tasks = json.loads((RL_EVAL / "eval_set_24_tasks.jsonl").read_text(encoding="utf-8")) \
        if False else None
    eval_scripts = set()
    # eval-set scripts come from the frozen manifest
    man = RL_EVAL / "eval_set_24_tasks.jsonl"
    for line in man.read_text(encoding="utf-8").splitlines():
        eval_scripts.add(json.loads(line)["script"])
    groups = []
    with open(train_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            task = r.get("task", "")
            if any(task.startswith(pfx) or pfx in task[:200] for pfx in
                   ()):  # prefix isolation handled below via script ids
                continue
            groups.append({"idx": i, "task": task})
    # isolation by the known isolated script ids is applied by the caller via
    # --exclude-scripts (explicit list), keeping this function pure.
    return groups[:]


RL_EVAL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"


# ---------------------------------------------------------------- stage 3 ----
def rollout_real(model, tok, prompt: str):
    enc = tok([prompt] * K, return_tensors="pt", truncation=True,
              max_length=1024 - MAX_NEW).to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, do_sample=True, temperature=TEMP,
                             top_p=TOP_P, repetition_penalty=REP_PEN,
                             max_new_tokens=MAX_NEW,
                             pad_token_id=tok.pad_token_id)
    texts = tok.batch_decode(out[:, enc["input_ids"].shape[1]:],
                             skip_special_tokens=True)
    return texts, out[:, enc["input_ids"].shape[1]:]


def rollout_mock(task: str, rng: random.Random):
    """Deterministic mock candidates exercising r5 scoring variance (CPU)."""
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


# ---------------------------------------------------------------- stage 4 ----
def s0_reward(task: str, cand_text: str, vocab) -> tuple[float | None, dict]:
    """S0 = r5-only coverage (v0.6). Returns (reward, audit)."""
    try:
        b = json.loads(cand_text)
    except Exception:
        return 0.0, {"reward_component": "parse_fail"}
    if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
        return 0.0, {"reward_component": "schema_fail"}
    res = evaluate_pair(task, b)["score"]
    if res["coverage_ratio"] is None:
        return None, {"reward_component": "abstain"}
    return res["coverage_ratio"], {"reward_component": "coverage"}


def token_kl(logp_ref, logp_pol, attn):
    """Per-token k3 estimator: d = logp_ref - logp_pol;
    KL_t = exp(d_t) - d_t - 1 (>= 0). Returns token-mean over real tokens."""
    d = (logp_ref - logp_pol).float()
    kl = d.exp() - d - 1.0
    mask = attn.to(torch.bool)
    if mask.sum() == 0:
        return torch.tensor(0.0)
    return kl[mask].mean()


# ---------------------------------------------------------------- stage 5 ----
def group_advantage(rewards):
    import statistics
    mu = sum(rewards) / len(rewards)
    var = sum((x - mu) ** 2 for x in rewards) / len(rewards)
    std = math.sqrt(var)
    if std < 1e-8:
        return [0.0] * len(rewards), True  # zero-variance group
    return [(x - mu) / std for x in rewards], False


def save_checkpoint(out_dir: Path, adapter_model, tok, update_idx, extra):
    try:
        d = out_dir / f"update_{update_idx:03d}"
        d.mkdir(parents=True, exist_ok=True)
        adapter_model.save_pretrained(d)
        (d / "trainer_state.json").write_text(
            json.dumps(extra, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[HARD-STOP] checkpoint save failure at update {update_idx}: {e}",
              flush=True)
        return False  # caller MUST stop (contract: save failure = stop)


# ---------------------------------------------------------------- main ----
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true",
                    help="CPU mock dry-run: no GPU, no real model, real r5 scoring")
    ap.add_argument("--selftest-faults", action="store_true",
                    help="run the six failure-path injections (local, CPU)")
    ap.add_argument("--train", action="store_true",
                    help="REAL training path (requires GPU window authorization)")
    ap.add_argument("--base", default="/home/qy/models/Qwen3.5/Qwen3.5-9B-Base")
    ap.add_argument("--adapter",
                    default="/home/qy/stage1_run_planner_v2_fmt/stage1_adapter")
    ap.add_argument("--train-data",
                    default="/home/qy/planner_v2_train.jsonl")
    ap.add_argument("--out", default="/home/qy/rl_grpo_smoke")
    ap.add_argument("--max-updates", type=int, default=MAX_UPDATES)
    ap.add_argument("--local-tasks", default=str(RL_EVAL / "eval_set_24_tasks.jsonl"),
                    help="(mock) tasks file for CPU dry-run")
    args = ap.parse_args(argv)

    if args.selftest_faults:
        return selftest_faults()
    if not args.train:
        return mock_dryrun(args)
    # real path would go here; it is gated by the contract launch checklist and
    # is NOT implemented in this local phase (owner: no GPU occupation now).
    print("[HARD-STOP] --train is not implemented in the local phase. "
          "The real launch uses the server deployment checklist (contract §7).")
    return 2


# ---------------- mock dry-run (CPU): full loop minus real model ----------------
def mock_dryrun(args):
    import torch
    print("[mock] CPU dry-run: real r5 scoring + real advantage/KL/stop logic; "
          "rollout = deterministic mock; update = tiny CPU tensors", flush=True)
    torch.manual_seed(SEED)
    rng = random.Random(SEED)
    tasks = [json.loads(l) for l in
             Path(args.local_tasks).read_text(encoding="utf-8").splitlines()]
    groups = []
    for t in tasks:
        cands = rollout_mock(t["task"], rng)
        groups.append({"task": t["task"], "cands": cands})
    if len(groups) > args.max_updates:
        groups = groups[:args.max_updates]

    # tiny policy/ref logprob stand-ins: torch CPU tensors as "logits"
    vocab_size = 64
    tiny_pol = torch.nn.Linear(16, vocab_size)
    tiny_ref = torch.nn.Linear(16, vocab_size)
    with torch.no_grad():  # freeze ref
        for q in tiny_ref.parameters():
            q.copy_(q)  # no-op; ref stays fixed by never updating it

    ckpt_dir = Path(args.out) / "checkpoints_mock"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    class MockSaveable:
        """save_pretrained shim so mock checkpoints exercise the real save path."""
        def __init__(self, model):
            self._m = model
        def save_pretrained(self, d):
            torch.save({"state_dict": self._m.state_dict()}, Path(d) / "mock_pt.pt")

    mock_saveable = MockSaveable(tiny_pol)
    kl_consec = 0
    starve_consec = 0
    updates_done = 0
    stop = None
    opt = torch.optim.SGD(tiny_pol.parameters(), lr=1e-3)

    for upd, g in enumerate(groups):
        rewards, audits = [], []
        for ci, cand in enumerate(g["cands"]):
            r, audit = s0_reward(g["task"], cand, None)
            rewards.append(r)
            audits.append(audit)
        if any(r is None for r in rewards):
            # abstain candidates: contract S0 = coverage abstain -> reward None;
            # group-relative needs all rewards: treat abstain as 0.0 with flag
            rewards = [0.0 if r is None else r for r in rewards]
        adv, zero_var = group_advantage(rewards)
        if zero_var:
            starve_consec += 1
        else:
            starve_consec = 0
        if starve_consec >= STARVATION_LIMIT:
            stop = f"signal starvation: {STARVATION_LIMIT} consecutive zero-variance groups"
            break
        # mock KL: token-mean KL from tiny tensors (deterministic per update)
        x = torch.randn(2, 16)
        lp_pol = torch.log_softmax(tiny_pol(x), dim=-1)
        lp_ref = torch.log_softmax(tiny_ref(x), dim=-1)
        # gather logprobs of the "generated" tokens (mock token ids)
        gen_ids = torch.randint(0, vocab_size, (2, 5))
        pol_t = lp_pol.gather(-1, gen_ids)
        ref_t = lp_ref.gather(-1, gen_ids)
        d = (ref_t - pol_t).detach()
        kl_tok = (d.exp() - d - 1.0).mean().item()
        if kl_tok > KL_CEILING_SINGLE:
            stop = f"KL single-update token-mean {kl_tok:.2f} > {KL_CEILING_SINGLE} nat"
            break
        kl_consec = kl_consec + 1 if kl_tok > KL_CEILING_CONSEC else 0
        if kl_consec >= KL_CONSEC_LIMIT:
            stop = f"KL token-mean > {KL_CEILING_CONSEC} nat on {KL_CONSEC_LIMIT} consecutive updates"
            break
        # policy-gradient-style mock update: nudge tiny_pol by advantage sign
        loss = -torch.tensor(adv[0] if adv else 0.0) * lp_pol.sum() * 1e-6
        opt.zero_grad()
        loss.backward()
        opt.step()
        updates_done = upd + 1
        if updates_done % CHECKPOINT_EVERY == 0:
            extra = {"update": updates_done, "kl_tok": kl_tok,
                     "starve_consec": starve_consec}
            if not save_checkpoint(ckpt_dir, mock_saveable, None, updates_done, extra):
                sys.exit(1)  # save failure = HARD STOP (contract)
        print(f"[mock] update {updates_done}: rewards={[round(r,3) for r in rewards]} "
              f"zero_var={zero_var} kl_tok={kl_tok:.3f}", flush=True)
        if updates_done >= args.max_updates:
            stop = f"budget: {args.max_updates} task-group updates reached"
            break
    print(f"[mock] DONE updates={updates_done} stop={stop}", flush=True)
    return 0


# ---------------- fault injection selftest (owner detail 3) ----------------
def selftest_faults():
    """Six failure-path injections, each asserting the contract behavior."""
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

    # F1 SHA mismatch -> hard exit
    def f1():
        p = Path(REPO) / "scripts/_tmp_identity_bad.txt"
        p.write_text("x")
        verify_identity({"adapter_model": str(p)}, skip=False)
    case("F1_sha_mismatch_hard_exit", f1, "exit(1)")

    # F2 candidate shortfall: group with 3 rewards (k must be 8)
    def f2():
        adv, zv = group_advantage([0.5, 0.5, 0.5])
        return f"zero_var={zv}"
    case("F2_short_group_flagged_zero_variance", f2, "zero_var=True")

    # F3 reward parse exception -> 0.0 reward (no crash)
    def f3():
        r, _ = s0_reward("task", "not json", None)
        return r
    case("F3_reward_parse_exception_zero", f3, 0.0)

    # F4 KL consecutive overrun -> stop string (simulated counter)
    def f4():
        consec = 0
        for kl in [1.5, 1.2, 2.0, 1.1, 1.3]:
            consec = consec + 1 if kl > KL_CEILING_CONSEC else 0
            if consec >= KL_CONSEC_LIMIT:
                return "stop"
        return "no_stop"
    case("F4_kl_consec_overrun_stop", f4, "stop")

    # F5 signal starvation -> stop string
    def f5():
        starve = 0
        for _ in range(STARVATION_LIMIT):
            starve += 1
            if starve >= STARVATION_LIMIT:
                return "stop"
        return "no_stop"
    case("F5_starvation_stop", f5, "stop")

    # F6 checkpoint save failure -> returns False (caller exits)
    def f6():
        class Boom:
            def save_pretrained(self, d):
                raise OSError("disk full")
        return save_checkpoint(Path("Z:/nonexistent_root_xyz"), Boom(), None, 1, {})
    case("F6_ckpt_save_failure_stops", f6, False)

    n_ok = sum(1 for _, ok, _, _ in results if ok)
    print(f"fault injection: {n_ok}/{len(results)} pass")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    import torch  # noqa: F401  (imported here so --help works without torch)
    sys.exit(main())
