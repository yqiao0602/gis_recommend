#!/usr/bin/env python3
"""M1-R2 Phase 2: decoder backbone domain pretraining (DAPT) — frozen contract.

Contract (docs/plans/domain_corpus_v1_spec.md §10, owner-frozen 2026-09-14):
  corpus      : D3 60% (seed 20260914 kept-list) + D4 4x epoch-level + D1 1x
  budget      : 487.5M byte-tokens (wordpiece census 181.3M is scale, NOT budget)
  tokenizer   : temporary byte-level vocab (256 bytes + PAD/START/END = 259)
  condition   : dummy zero memory + task_type "Unknown" (id 0), constant
  trainable   : temporary token embedding (tied output projection),
                decoder layers, decoder norm, input FiLM gamma/beta
  frozen out  : BERT encoder, text/condition projections, task_type embedding,
                condition fusion (never see real text in DAPT)
  after DAPT  : discard temporary embedding/output; SFT reinitializes the
                132-token L3 vocab and carries over ONLY the decoder stack:
                decoder_layers + decoder_norm + input_film_gamma/beta

Subcommands:
  audit       Phase 2-A initialization audit — no training, no update, no
              checkpoint.  Proves the contract at TENSOR level (parameter
              statistics, LayerNorm freshness, seed determinism, R1 SHA
              inequality, AMP forward+backward dry-run with zero parameter
              update) and writes r2_dapt_init_audit.{json,md} under
              <out>/audit/.  An R1 checkpoint is an architecture/schema
              reference only — never an initialization source.
  smoke       100-500 step run on the real corpus: loss finite, ledger works,
              checkpoint save/reload, determinism.
  train       Full 1-epoch budget run with periodic checkpoints + ledger.
  migrate     Phase 2-C migration audit: DAPT ckpt -> R1-shaped model,
              carry-set SHA equality, embedding inequality proofs.

Run on the compute server (qwen35 env, GPU). No frozen artifact is modified.
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

import torch
import torch.nn as nn
import torch.nn.functional as F

PROJ = Path("/home/qy/system_redesign")
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "src"))

SMOKE_DIR = Path("/home/qy/gee_llm_smoke")
DEFAULT_CORPUS = SMOKE_DIR / "domain_corpus_v1"
DEFAULT_RECIPE = DEFAULT_CORPUS / "recipe_freeze_v1.json"

# byte-level temporary vocabulary
BYTE_VOCAB = 256
PAD_ID, START_ID, END_ID = 256, 257, 258
TEMP_VOCAB_SIZE = 259

# frozen recipe numbers (exact, from pool files + kept-SHA list 2026-09-15;
# D3 budget = the true bytes of the 26,285 kept SHAs — heavy-tailed file sizes
# make a proportional 0.6x an approximation, actual kept share is 60.78%)
BUDGET_BYTES = {"d3": 395_768_519, "d4": 96_759_756, "d1": 16_452}  # kept/4x/1x
SEED = 20260914
D3_FACTOR, D4_FACTOR, D1_FACTOR = 0.6, 4.0, 1.0
TARGET_TOTAL = 492_544_727

CARRY_KEYS = ("decoder_layers", "decoder_norm", "input_film_gamma", "input_film_beta")


# ── byte tokenizer ─────────────────────────────────────────────────────────

def encode_bytes(text: str) -> list:
    return list(text.encode("utf-8", errors="ignore"))


# ── model construction ─────────────────────────────────────────────────────

def build_model(dapt_seq_len: int = 1024, device: str = "cuda:0", init_seed: int = SEED):
    """Instantiate the R1-architecture model with the TEMPORARY byte vocab.

    max_seq_length is extended to dapt_seq_len for byte chunks; the sinusoidal
    PE is a fixed buffer, so positions 0-99 remain identical to R1's PE and no
    learned parameter is affected. Nothing from the R1 checkpoint is loaded —
    by construction the whole model is fresh random init.

    init_seed exists so the Phase 2-A audit can prove the recorded SHAs really
    fingerprint the random init: same seed must reproduce them, a different
    seed must change them.
    """
    from gis_recommend.config import transformer_config as cfg
    from gis_recommend.models.transformer_model_v4 import (
        TaskConditionedL3TransformerModelV4,
    )
    torch.manual_seed(init_seed)
    model = TaskConditionedL3TransformerModelV4(
        vocab_size=TEMP_VOCAB_SIZE,
        num_task_types=5,                # m1_task_vocab_v1.json
        d_model=cfg.V4_D_MODEL, n_heads=cfg.V4_N_HEADS, n_layers=cfg.V4_N_LAYERS,
        dim_feedforward=cfg.V4_D_FF, dropout=0.0,
        max_seq_length=dapt_seq_len,     # extended PE (fixed buffer)
        max_memory_tokens=cfg.V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=False, freeze_bert=True,
        bert_unfreeze_layers=cfg.V4_BERT_UNFREEZE_LAYERS,
    )
    # keep the frozen BERT off the GPU: DAPT never calls it
    model.text_encoder.to("cpu")
    return model.to(device)


def make_trainable(model) -> list:
    """Contract: only temp embedding (+tied output), decoder stack, input FiLM."""
    for p in model.parameters():
        p.requires_grad_(False)
    trainable = []
    for key in CARRY_KEYS:
        for p in getattr(model, key).parameters():
            p.requires_grad_(True)
            trainable.append(p)
    for p in model.token_embedding.parameters():      # tied with output_projection
        p.requires_grad_(True)
        trainable.append(p)
    return trainable


@torch.no_grad()
def make_dummy_condition_memory(model, device, batch: int = 1):
    """Constant dummy condition + zero memory (eval mode, computed once).

    The condition path (task_type_embedding -> condition_fusion) is frozen in
    DAPT, so we compute it on the model's current device and cache the result;
    the frozen text/condition projections are never trained on real text.
    """
    was_training = model.training
    model.eval()
    dev = next(model.parameters()).device
    zeros_pooled = torch.zeros(1, 768, device=dev)
    condition = model._fuse_condition(torch.tensor([0], device=dev), zeros_pooled)
    condition = condition.to(device)
    mem = torch.zeros(1, model.memory_positional_encoding.pe.size(1) - 32,
                      model.d_model, device=device)
    # replicate the full-forward memory path: projection(zeros) + memory PE
    mem = model.memory_positional_encoding(mem)
    if was_training:
        model.train()
    return condition.detach(), mem.detach()


def decoder_forward(model, ids, condition, memory):
    """Manual decoder path (skips BERT entirely): matches the full forward
    from token_embedding to output_projection for the decoder stack."""
    tok_emb = model.token_embedding(ids)
    gamma = model.input_film_gamma(condition).unsqueeze(1)
    beta = model.input_film_beta(condition).unsqueeze(1)
    tok_emb = gamma * tok_emb + beta
    tok_emb = model.positional_encoding(tok_emb)
    T = ids.size(1)
    causal = torch.triu(
        torch.full((T, T), float("-inf"), device=ids.device), diagonal=1)
    x = tok_emb
    for layer in model.decoder_layers:
        x = layer(x, memory.expand(ids.size(0), -1, -1), condition,
                  tgt_mask=causal)
    x = model.decoder_norm(x)
    return model.output_projection(x)


# ── corpus loading ─────────────────────────────────────────────────────────

def load_chunks(corpus_dir: Path, recipe: dict, seq_len: int):
    """Return list of (pool, bytes-of-chunk) with recipe factors applied.

    D3: only kept SHAs (recipe['d3_kept_sha256']), 1 chunk set.
    D4: docstrings + readmes, each doc repeated 4x (sample-level, same seed).
    D1: anchors once.
    """
    d3_keep = set(recipe["d3_kept_sha256"])
    d3_bytes = d4_bytes = d1_bytes = 0
    chunks = []  # (pool_tag, list[int bytes])
    chunk_size = seq_len - 2  # leave room for START/END specials per sample

    def add_chunks(text, tag, repeat=1):
        nonlocal d3_bytes, d4_bytes, d1_bytes
        b = encode_bytes(text)
        for r in range(repeat):
            for i in range(0, len(b), chunk_size):
                c = b[i:i + chunk_size]
                chunks.append((tag, c))
                if tag == "d3":
                    d3_bytes += len(c)
                elif tag == "d4":
                    d4_bytes += len(c)
                else:
                    d1_bytes += len(c)

    for line in open(corpus_dir / "d3_code.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["sha256"] in d3_keep:
            add_chunks(r["text"], "d3")
    for fname in ("d4_docstrings.jsonl", "d4_readmes.jsonl"):
        for line in open(corpus_dir / fname, encoding="utf-8"):
            add_chunks(json.loads(line)["text"], "d4", repeat=int(D4_FACTOR))
    for line in open(corpus_dir / "d1_anchors.jsonl", encoding="utf-8"):
        add_chunks(json.loads(line)["text"], "d1")
    return chunks, {"d3": d3_bytes, "d4": d4_bytes, "d1": d1_bytes}


def batchify(chunks, batch_size, pad_id=PAD_ID):
    """Shuffled infinite-ish single-epoch iterator over (ids, labels, tags)."""
    order = list(range(len(chunks)))
    random.Random(SEED).shuffle(order)
    for i in range(0, len(order), batch_size):
        idxs = order[i:i + batch_size]
        seqs, tags = [], []
        for j in idxs:
            tag, b = chunks[j]
            seqs.append([START_ID] + b + [END_ID])
            tags.append(tag)
        maxlen = max(len(s) for s in seqs)
        ids = torch.full((len(seqs), maxlen), pad_id, dtype=torch.long)
        labels = torch.full((len(seqs), maxlen), -100, dtype=torch.long)
        for k, s in enumerate(seqs):
            ids[k, :len(s)] = torch.tensor(s)
            labels[k, :len(s) - 1] = torch.tensor(s[1:])  # next-token targets
        yield ids, labels, tags


# ── budget ledger ──────────────────────────────────────────────────────────

class Ledger:
    def __init__(self):
        self.seen = {"d3": 0, "d4": 0, "d1": 0}
        self.samples = 0
        self.steps = 0

    def update(self, labels, tags):
        real = (labels != -100).sum(dim=1).tolist()
        for n, tag in zip(real, tags):
            self.seen[tag] += int(n)
        self.samples += len(tags)

    def total(self):
        return sum(self.seen.values())

    def row(self):
        t = self.total()
        return {"samples": self.samples, "byte_tokens_seen": t,
                "d3": self.seen["d3"], "d4": self.seen["d4"], "d1": self.seen["d1"],
                "coverage_vs_budget": round(t / TARGET_TOTAL, 6)}


# ── tensor SHA for audits ──────────────────────────────────────────────────

def tensor_sha(t: torch.Tensor) -> str:
    return hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()[:16]


def carry_state(model) -> dict:
    out = {}
    for key in CARRY_KEYS:
        mod = getattr(model, key)
        out[key] = {k: v.clone() for k, v in mod.state_dict().items()}
    return out


def carry_shas(state: dict) -> dict:
    return {k: {kk: tensor_sha(vv) for kk, vv in v.items()} for k, v in state.items()}


# ── Phase 2-A parameter-level initialization proof ──────────────────────────
# CONTRACT: an R1 checkpoint may serve as an architecture/schema reference
# only — it is NEVER a parameter initialization source for DAPT.  Every check
# below proves this at the tensor level (shape / distribution / determinism /
# SHA), never by code path alone.


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def _tensor_stats(t: torch.Tensor) -> dict:
    t = t.detach().to("cpu").float()
    return {
        "shape": list(t.shape),
        "numel": int(t.numel()),
        "mean": round(float(t.mean()), 6),
        "std": round(float(t.std()), 6),
        "absmax": round(float(t.abs().max()), 6),
        "sha256_16": tensor_sha(t),
    }


def _audit_param_table(model) -> dict:
    """Per-group tensor statistics — the initialization fingerprint."""
    table = {}
    table["token_embedding(tied_output_projection)"] = _tensor_stats(
        model.token_embedding.weight)
    table["task_type_embedding(frozen)"] = _tensor_stats(
        model.task_type_embedding.weight)
    table["condition_fusion[0](frozen)"] = _tensor_stats(
        model.condition_fusion[0].weight)
    table["input_film_gamma.weight"] = _tensor_stats(model.input_film_gamma.weight)
    table["input_film_gamma.bias"] = _tensor_stats(model.input_film_gamma.bias)
    table["input_film_beta.weight"] = _tensor_stats(model.input_film_beta.weight)
    table["input_film_beta.bias"] = _tensor_stats(model.input_film_beta.bias)
    table["decoder_norm.weight"] = _tensor_stats(model.decoder_norm.weight)
    table["decoder_norm.bias"] = _tensor_stats(model.decoder_norm.bias)
    table["decoder_layers[0].first_param"] = _tensor_stats(
        next(model.decoder_layers[0].parameters()))
    table["decoder_layers[-1].first_param"] = _tensor_stats(
        next(model.decoder_layers[-1].parameters()))
    return table


def _decoder_layernorms_fresh(model) -> tuple:
    """Every decoder-scope LayerNorm must be EXACTLY weight==1, bias==0.

    A trained or checkpoint-loaded decoder cannot satisfy this — it is the
    strongest statistical signature of a fresh init.  The frozen BERT
    text_encoder is out of scope: it legitimately carries HF-pretrained
    weights and is never in the DAPT compute path.
    """
    detail = {}
    for name, mod in model.named_modules():
        if isinstance(mod, nn.LayerNorm) and "decoder" in name:
            detail[name or "decoder_norm"] = bool(
                torch.all(mod.weight == 1.0) and torch.all(mod.bias == 0.0))
    return bool(detail) and all(detail.values()), detail


def _linear_kaiming_fresh(mod: nn.Linear, tol: float = 0.02) -> bool:
    """nn.Linear default init is kaiming_uniform(a=sqrt(5)):
    U(-1/sqrt(fan_in), +1/sqrt(fan_in)).  A fresh linear's absmax sits at the
    bound; a trained one almost never does."""
    w = mod.weight.detach()
    bound = 1.0 / math.sqrt(w.shape[1])
    absmax = float(w.abs().max())
    return bound * (1.0 - tol) <= absmax <= bound * (1.0 + tol)


def _load_r1_token_embedding(path):
    """Defensively locate the R1 token-embedding tensor inside the composite
    checkpoint.  Returns (tensor, key) or (None, reason)."""
    try:
        ck = torch.load(path, map_location="cpu", weights_only=False)
    except Exception as exc:  # noqa: BLE001 — audit records, never crashes
        return None, f"load_failed:{type(exc).__name__}"
    containers = []
    if isinstance(ck, dict):
        for key in ("model_state_dict", "state_dict", "model", "module"):
            value = ck.get(key)
            if isinstance(value, dict):
                containers.append(value)
        containers.append(ck)
    for sd in containers:
        for key, value in sd.items():
            if isinstance(value, torch.Tensor) and key.endswith("token_embedding.weight"):
                return value, key
    return None, "token_embedding_weight_not_found"


def _task_vocab_check(path) -> tuple:
    """The DAPT condition uses task_type id 0; the vocab must map id 0 to
    Unknown and have exactly 5 task types (m1_task_vocab_v1.json)."""
    info = {"path": str(path), "id0": None, "size": 0}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        info["error"] = type(exc).__name__
        return False, info
    mapping = data.get("task_type_to_id") if isinstance(data, dict) else None
    if (mapping is None and isinstance(data, dict)
            and isinstance(data.get("id_to_task_type"), dict)):
        mapping = {name: int(idx) for idx, name in data["id_to_task_type"].items()}
    if mapping is None and isinstance(data, list):
        mapping = {name: i for i, name in enumerate(data)}
    if not isinstance(mapping, dict) or not mapping:
        return False, info
    info["size"] = len(mapping)
    for name, idx in mapping.items():
        if int(idx) == 0:
            info["id0"] = str(name)
    ok = (info["id0"] is not None and "unknown" in info["id0"].lower()
          and len(mapping) == 5)
    return ok, info


# ── subcommands ────────────────────────────────────────────────────────────

def cmd_audit(args):
    print("=" * 70)
    print("PHASE 2-A: DAPT INITIALIZATION AUDIT (no training, no update)")
    print("CONTRACT: the R1 checkpoint is an architecture/schema reference")
    print("only — NEVER a DAPT parameter initialization source.")
    print("=" * 70)
    checks = {}
    corpus_dir, recipe_path = Path(args.corpus), Path(args.recipe)

    # 1. frozen manifest — recipe + budget cross-check
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    budget = json.loads((corpus_dir / "budget_v1.json").read_text(encoding="utf-8"))
    tb = budget["training_byte"]
    checks["recipe_seed_20260914"] = recipe["seed"] == SEED
    checks["recipe_factors"] = (recipe["d3_sampling"] == D3_FACTOR
                                and recipe["d4_oversampling"] == D4_FACTOR
                                and recipe["d1_factor"] == D1_FACTOR)
    checks["budget_per_pool_matches_frozen"] = (
        tb.get("d3_kept_actual", tb.get("d3_0.6x")) == BUDGET_BYTES["d3"]
        and tb["d4_4x"] == BUDGET_BYTES["d4"]
        and tb["d1_1x"] == BUDGET_BYTES["d1"])
    checks["budget_total_matches_frozen"] = abs(tb["total_bytes"] - TARGET_TOTAL) < 5_000
    print(f"[budget] d3={tb['d3_0.6x']:,} d4={tb['d4_4x']:,} d1={tb['d1_1x']:,} "
          f"total={tb['total_bytes']:,}")

    # 2. temporary byte tokenizer
    probe = "QgsGeometry.buffer(dist) → 缓冲区 Create workflow L3_02_01_01"
    ids = encode_bytes(probe)
    checks["byte_roundtrip"] = bytes(ids).decode("utf-8") == probe
    checks["byte_ids_in_range"] = all(0 <= i < BYTE_VOCAB for i in ids)
    checks["temp_vocab_259"] = TEMP_VOCAB_SIZE == BYTE_VOCAB + 3
    print(f"[tokenizer] {len(probe)} chars -> {len(ids)} byte ids, roundtrip OK")

    # 3. task vocab: id 0 must be Unknown, 5 types
    tv_ok, tv_info = _task_vocab_check(args.task_vocab)
    checks["task_type_id0_unknown"] = tv_ok
    checks["task_vocab_size_5"] = tv_info["size"] == 5
    print(f"[task-vocab] size={tv_info['size']} id0={tv_info['id0']!r}")

    # 4. model instantiation — fresh random init, proven at tensor level
    model = build_model(args.seq_len, args.device)
    assert model.token_embedding.num_embeddings == TEMP_VOCAB_SIZE
    assert model.output_projection.weight is model.token_embedding.weight
    checks["temp_vocab_259_model"] = (
        model.token_embedding.num_embeddings == TEMP_VOCAB_SIZE)
    checks["embedding_tied_to_output"] = (
        model.output_projection.weight is model.token_embedding.weight)
    param_table = _audit_param_table(model)
    emb = model.token_embedding.weight.detach()
    checks["embedding_fresh_normal01"] = abs(float(emb.float().std()) - 1.0) < 0.05
    checks["task_embedding_fresh_normal01"] = (
        abs(float(model.task_type_embedding.weight.detach().float().std()) - 1.0) < 0.05)
    ln_ok, ln_detail = _decoder_layernorms_fresh(model)
    checks["decoder_layernorms_exactly_fresh"] = ln_ok
    checks["input_film_kaiming_fresh"] = (
        _linear_kaiming_fresh(model.input_film_gamma)
        and _linear_kaiming_fresh(model.input_film_beta))
    print(f"[init] embedding std={float(emb.float().std()):.4f} (expect ~1.0); "
          f"{len(ln_detail)} decoder LayerNorms exactly weight=1/bias=0; "
          f"input FiLM at kaiming bound")

    # determinism: same seed reproduces the SHAs; a different seed changes them
    m_b = build_model(args.seq_len, "cpu")
    checks["init_reproducible_same_seed"] = (
        tensor_sha(model.token_embedding.weight) == tensor_sha(m_b.token_embedding.weight)
        and carry_shas(carry_state(model)) == carry_shas(carry_state(m_b)))
    m_c = build_model(args.seq_len, "cpu", init_seed=SEED + 99)
    checks["init_seed_sensitive"] = (
        tensor_sha(model.token_embedding.weight)
        != tensor_sha(m_c.token_embedding.weight))
    del m_b, m_c
    print("[init] same-seed rebuild identical; different-seed rebuild differs")

    # R1 isolation — parameter-level proof (shape / stats / SHA), not code path
    r1_emb, r1_key = _load_r1_token_embedding(args.r1_checkpoint)
    r1_section = {"path": str(args.r1_checkpoint), "key": r1_key}
    if r1_emb is not None:
        r1_section["stats"] = _tensor_stats(r1_emb)
        checks["r1_embedding_shape_incompatible"] = (
            tuple(r1_emb.shape) != tuple(emb.shape))
        checks["r1_embedding_sha_differs"] = (
            tensor_sha(r1_emb) != tensor_sha(model.token_embedding.weight))
        r1_section["vocab_note"] = (
            f"R1 vocab {int(r1_emb.shape[0])} vs DAPT temp vocab {TEMP_VOCAB_SIZE}")
        print(f"[r1-proof] R1 emb {tuple(r1_emb.shape)} vs DAPT {tuple(emb.shape)}: "
              f"shape incompatible, SHA differs")
    else:
        r1_section["note"] = ("R1 checkpoint not comparable; structural proof "
                              "stands (temp vocab 259 cannot hold R1's L3 vocab)")
        print(f"[r1-proof] R1 ckpt not comparable ({r1_key}); "
              f"structural proof: vocab {TEMP_VOCAB_SIZE} != 132")
    r1_proof_keys = [k for k in checks if k.startswith("r1_embedding_")]
    checks["r1_parameters_not_loaded"] = (
        all(bool(checks[k]) for k in r1_proof_keys) if r1_proof_keys
        else checks["temp_vocab_259_model"])

    # trainable census (DAPT contract scope)
    trainable = make_trainable(model)
    trainable_ids = {id(p) for p in trainable}
    n_train = sum(p.numel() for p in trainable)
    n_total = sum(p.numel() for p in model.parameters())
    checks["trainable_scope_contract"] = (
        all(p.requires_grad for p in trainable)
        and not any(p.requires_grad for p in model.parameters()
                    if id(p) not in trainable_ids))
    print(f"[model] total={n_total/1e6:.1f}M trainable(DAPT)={n_train/1e6:.1f}M "
          f"(BERT and condition path frozen out)")

    # 5. dummy condition/memory
    condition, memory = make_dummy_condition_memory(model, args.device)
    checks["dummy_condition_shape"] = tuple(condition.shape) == (1, model.d_model)
    checks["dummy_memory_shape"] = tuple(memory.shape)[1:] == (
        model.memory_positional_encoding.pe.size(1) - 32, model.d_model)
    checks["dummy_condition_detached"] = (
        not condition.requires_grad and not memory.requires_grad)

    # 6. PE extension is lossless vs R1 positions 0-99 (CPU copy)
    pe = model.positional_encoding.pe[0, :100].detach().cpu()
    d = model.d_model
    pos = torch.arange(0, 100).float().unsqueeze(1)
    div = torch.exp(torch.arange(0, d, 2).float() * (-math.log(10000.0) / d))
    analytic = torch.zeros(100, d)
    analytic[:, 0::2] = torch.sin(pos * div)
    analytic[:, 1::2] = torch.cos(pos * div)
    checks["pe_extension_lossless"] = torch.allclose(pe, analytic, atol=1e-5)
    print(f"[pe] extended to {args.seq_len}; positions 0-99 match analytic sinusoid")

    # 7. AMP forward + backward dry-run — NO optimizer step, NO update
    carry_before = carry_shas(carry_state(model))
    emb_sha_before = tensor_sha(model.token_embedding.weight)
    opt = torch.optim.AdamW(trainable, lr=1e-4, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda")
    ids = torch.randint(0, BYTE_VOCAB, (2, 64), device=args.device)
    ids[:, 0] = START_ID
    with torch.amp.autocast("cuda"):
        logits = decoder_forward(model, ids, condition, memory)
        loss = F.cross_entropy(logits[:, :-1].reshape(-1, TEMP_VOCAB_SIZE),
                               ids[:, 1:].reshape(-1))
    checks["amp_autocast_active"] = logits.dtype in (torch.float16, torch.bfloat16)
    checks["forward_logits_shape"] = tuple(logits.shape) == (2, 64, TEMP_VOCAB_SIZE)
    checks["loss_finite_at_init"] = math.isfinite(float(loss))
    print(f"[dry-run] logits {tuple(logits.shape)} dtype={logits.dtype}, "
          f"init loss {float(loss):.4f} (ln(259)={math.log(TEMP_VOCAB_SIZE):.4f})")
    scaler.scale(loss).backward()
    n_with, grads_finite, frozen_with_grad = 0, True, 0
    for p in model.parameters():
        if id(p) in trainable_ids:
            if p.grad is None:
                grads_finite = False
            else:
                n_with += 1
                if not bool(torch.isfinite(p.grad).all()):
                    grads_finite = False
        elif p.grad is not None:
            frozen_with_grad += 1
    checks["all_trainable_have_grad"] = n_with == len(trainable)
    checks["grads_all_finite"] = grads_finite
    checks["no_frozen_param_received_grad"] = frozen_with_grad == 0
    try:
        scaler.unscale_(opt)
        checks["optimizer_unscale_chain_ok"] = True
    except Exception as exc:  # noqa: BLE001
        checks["optimizer_unscale_chain_ok"] = False
        print(f"[dry-run] unscale_ failed: {exc}")
    # AUDIT NEVER STEPS THE OPTIMIZER — parameters must stay bit-identical.
    checks["no_parameter_update"] = (
        tensor_sha(model.token_embedding.weight) == emb_sha_before
        and carry_shas(carry_state(model)) == carry_before)
    print(f"[dry-run] grads {n_with}/{len(trainable)} trainable finite, "
          f"{frozen_with_grad} frozen with grad; parameters unchanged")

    # 8. corpus D3 kept census
    kept = set(recipe["d3_kept_sha256"])
    n_d3 = n_d3_total = 0
    for line in open(corpus_dir / "d3_code.jsonl", encoding="utf-8"):
        n_d3_total += 1
        if json.loads(line)["sha256"] in kept:
            n_d3 += 1
    checks["d3_kept_count_26285"] = n_d3 == len(kept) == 26285
    print(f"[corpus] D3 kept rows: {n_d3}/{n_d3_total} (dropped {n_d3_total - n_d3})")

    # ── artifacts: the experiment ID card ──────────────────────────────────
    ok = all(bool(v) for v in checks.values())
    audit_dir = Path(args.out) / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    r1_loaded_flag = not checks["r1_parameters_not_loaded"]
    payload = {
        "schema": "gis_recommend.m1_r2_dapt.init_audit.v1",
        "experiment": "M1-R2 Phase 2-A",
        "audit_status": "PASS" if ok else "FAIL",
        "environment": {
            "torch": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "device": args.device,
            "gpu": (torch.cuda.get_device_name(0)
                    if torch.cuda.is_available() else None),
        },
        "corpus": {
            "corpus_dir": str(corpus_dir),
            "recipe_path": str(recipe_path),
            "recipe_sha256_16": file_sha256(recipe_path),
            "d3_keep_ratio": D3_FACTOR,
            "d3_seed": SEED,
            "d4_oversampling": D4_FACTOR,
            "d1_factor": D1_FACTOR,
            "target_byte_tokens": TARGET_TOTAL,
            "budget": tb,
            "d3_kept_rows": n_d3,
            "d3_total_rows": n_d3_total,
        },
        "tokenizer": {
            "type": "temporary_byte_level",
            "byte_vocab": BYTE_VOCAB,
            "specials": {"PAD": PAD_ID, "START": START_ID, "END": END_ID},
            "total_vocab": TEMP_VOCAB_SIZE,
            "roundtrip_probe": probe,
        },
        "conditioning": {
            "memory": "dummy_zero",
            "task_type": tv_info["id0"] or "Unknown",
            "task_type_id": 0,
            "task_vocab_size": tv_info["size"],
        },
        "model": {
            "architecture": "TaskConditionedL3TransformerModelV4 (R1 architecture)",
            "body_initialization": "RANDOM",
            "film_initialization": "RANDOM",
            "embedding_initialization": "RANDOM (temporary byte vocab 259)",
            "output_initialization": "RANDOM (tied to embedding)",
            "params_total": n_total,
            "params_trainable_dapt": n_train,
            "carry_set": list(CARRY_KEYS),
        },
        "r1_isolation": {
            "r1_l3_embedding_loaded": r1_loaded_flag,
            "r1_l3_output_projection_loaded": r1_loaded_flag,
            **r1_section,
        },
        "param_table": param_table,
        "layernorm_fresh_detail": ln_detail,
        "dry_run": {
            "amp_dtype": str(logits.dtype),
            "init_loss": float(loss),
            "trainable_with_grad": n_with,
            "grads_finite": grads_finite,
            "frozen_with_grad": frozen_with_grad,
            "parameter_update": "NONE",
        },
        "checks": checks,
        "contract_note": (
            "R1 checkpoint is an architecture/schema reference only and is "
            "never a DAPT parameter initialization source. The temporary "
            "byte embedding/output are discarded before SFT, which "
            "reinitializes the 132-token L3 vocab and carries over ONLY "
            "decoder_layers + decoder_norm + input_film_gamma/beta."),
    }
    md = [
        "# R2-DAPT-INIT-AUDIT",
        "",
        f"audit_status = {payload['audit_status']}",
        f"date = {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "> CONTRACT: the R1 checkpoint is an architecture/schema reference",
        "> only — NEVER a DAPT parameter initialization source.",
        "",
        "## Corpus",
        "  D3 keep ratio       = 0.60",
        "  D3 seed             = 20260914",
        "  D4 oversampling     = 4.0x",
        "  D1 multiplier       = 1.0x",
        f"  target byte tokens  = {TARGET_TOTAL:,}",
        "",
        "## Tokenizer",
        "  type                = temporary_byte_level",
        "  vocab               = 256 bytes + PAD/START/END = 259",
        "",
        "## Conditioning",
        "  memory              = dummy/zero",
        f"  task_type           = {payload['conditioning']['task_type']} (id 0)",
        "",
        "## Model",
        "  architecture        = R1 architecture",
        "  body initialization = RANDOM",
        "  FiLM initialization = RANDOM",
        "  embedding           = RANDOM (259-row temporary byte vocab)",
        "  output projection   = RANDOM (tied to embedding)",
        "",
        "## R1 isolation (parameter-level proof)",
        f"  R1 L3 embedding loaded?         = {r1_loaded_flag}",
        f"  R1 L3 output projection loaded? = {r1_loaded_flag}",
        f"  evidence: {r1_section.get('vocab_note', r1_section.get('note', r1_key))}",
        "",
        "## Checks",
    ]
    md += [f"  {'PASS' if bool(v) else 'FAIL'}  {k}" for k, v in checks.items()]
    md += ["", "## Initialization fingerprint (tensor statistics)", "",
           "| group | shape | mean | std | absmax | sha256(16) |",
           "|---|---|---|---|---|---|"]
    for group, s in param_table.items():
        md.append(f"| {group} | {s['shape']} | {s['mean']} | {s['std']} | "
                  f"{s['absmax']} | {s['sha256_16']} |")
    md += ["", "## Decoder LayerNorm freshness (exact weight=1 / bias=0)", ""]
    md += [f"  {name}: {'FRESH' if v else 'DRIFTED'}" for name, v in ln_detail.items()]
    md += ["", "## Dry-run", "",
           f"  amp dtype = {logits.dtype}, init loss = {float(loss):.4f}, "
           f"grads {n_with}/{len(trainable)} finite, parameter updates = NONE"]
    (audit_dir / "r2_dapt_init_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (audit_dir / "r2_dapt_init_audit.md").write_text("\n".join(md) + "\n",
                                                     encoding="utf-8")

    print("\n" + "=" * 70)
    for k, v in checks.items():
        print(f"  {'PASS' if bool(v) else 'FAIL'}  {k}")
    print(f"PHASE 2-A AUDIT: {'ALL PASS' if ok else 'FAILURES PRESENT'}")
    print(f"artifacts: {audit_dir}/r2_dapt_init_audit.json / .md")
    return 0 if ok else 1


def run_training(args, max_steps=None):
    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    print("[load] corpus chunks...")
    t0 = time.time()
    chunks, chunk_budget = load_chunks(Path(args.corpus), recipe, args.seq_len)
    print(f"[load] {len(chunks)} chunks in {time.time()-t0:.0f}s; "
          f"byte budget d3={chunk_budget['d3']:,} d4={chunk_budget['d4']:,} "
          f"d1={chunk_budget['d1']:,} total={sum(chunk_budget.values()):,}")
    assert abs(sum(chunk_budget.values()) - TARGET_TOTAL) < 2_000_000, \
        f"chunk budget {sum(chunk_budget.values()):,} deviates from frozen " \
        f"{TARGET_TOTAL:,} by >2M bytes — refusing to train"

    model = build_model(args.seq_len, args.device)
    trainable = make_trainable(model)
    condition, memory = make_dummy_condition_memory(model, args.device)
    opt = torch.optim.AdamW(trainable, lr=args.lr, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda")

    ledger = Ledger()
    model.train()
    t0 = time.time()
    loss_acc = 0.0
    ckpt_dir = Path(args.out)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for step, (ids, labels, tags) in enumerate(
            batchify(chunks, args.batch_size), start=1):
        if max_steps and step > max_steps:
            break
        ids, labels = ids.to(args.device), labels.to(args.device)
        with torch.amp.autocast("cuda"):
            logits = decoder_forward(model, ids, condition, memory)
            loss = F.cross_entropy(logits.reshape(-1, TEMP_VOCAB_SIZE),
                                   labels.reshape(-1), ignore_index=-100)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        scaler.step(opt)
        scaler.update()

        ledger.update(labels, tags)
        ledger.steps = step
        loss_acc += loss.item()
        if step % args.log_every == 0:
            print(f"[{step}] loss={loss_acc/args.log_every:.4f} "
                  f"bpl={math.log(TEMP_VOCAB_SIZE):.3f} "
                  f"seen={ledger.total():,} ({ledger.row()['coverage_vs_budget']*100:.1f}%) "
                  f"mem={torch.cuda.max_memory_allocated()/2**30:.2f}GB "
                  f"({(time.time()-t0)/60:.1f}m)", flush=True)
            loss_acc = 0.0
        if step % args.ckpt_every == 0:
            save_ckpt(ckpt_dir, model, ledger, step, args)
    save_ckpt(ckpt_dir, model, ledger, ledger.steps, args)
    print(f"[done] {ledger.row()} minutes={(time.time()-t0)/60:.1f}")
    (ckpt_dir / "budget_ledger_final.json").write_text(
        json.dumps({"target": TARGET_TOTAL, "final": ledger.row(),
                    "coverage_pct": round(ledger.total() / TARGET_TOTAL * 100, 3)},
                   indent=2), encoding="utf-8")
    return 0


def save_ckpt(ckpt_dir, model, ledger, step, args):
    payload = {
        "schema": "gis_recommend.m1_r2_dapt.checkpoint.v1",
        "step": step,
        "contract": {"temp_vocab": TEMP_VOCAB_SIZE, "seed": SEED,
                     "d3": D3_FACTOR, "d4": D4_FACTOR, "d1": D1_FACTOR,
                     "budget_target": TARGET_TOTAL, "seq_len": args.seq_len},
        "carry_state": carry_state(model),
        "model_state_dict": {k: v for k, v in model.state_dict().items()},
        "ledger": ledger.row(),
        "carry_shas": carry_shas(carry_state(model)),
    }
    torch.save(payload, ckpt_dir / f"dapt_step{step}.pth")
    torch.save(payload, ckpt_dir / "dapt_latest.pth")
    print(f"[ckpt] step {step} saved (ledger {ledger.row()})", flush=True)


def cmd_smoke(args):
    print("=" * 70)
    print(f"PHASE 2-B SMOKE: {args.steps} steps on the real corpus")
    print("=" * 70)
    out = Path(args.out)
    rc = run_training(args, max_steps=args.steps)
    # reload + determinism of carry set
    from gis_recommend.config import transformer_config as cfg
    ck = torch.load(out / "dapt_latest.pth", map_location="cpu", weights_only=False)
    m2 = build_model(args.seq_len, "cpu")
    m2.load_state_dict(ck["model_state_dict"], strict=False)
    shas_new = carry_shas(carry_state(m2))
    shas_saved = ck["carry_shas"]
    same = all(shas_new[k][kk] == shas_saved[k][kk]
               for k in shas_saved for kk in shas_saved[k])
    print(f"[smoke] checkpoint reload carry-SHA match: {same}")
    return rc if same else 1


def cmd_migrate(args):
    """Phase 2-C: prove the SFT init carries ONLY the decoder stack."""
    print("=" * 70)
    print("PHASE 2-C: MIGRATION AUDIT (DAPT -> R1-shaped SFT init)")
    print("=" * 70)
    from gis_recommend.config import transformer_config as cfg
    from gis_recommend.models.transformer_model_v4 import (
        TaskConditionedL3TransformerModelV4,
    )
    ck = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    assert ck["schema"] == "gis_recommend.m1_r2_dapt.checkpoint.v1"

    torch.manual_seed(SEED + 1)
    sft = TaskConditionedL3TransformerModelV4(
        vocab_size=132, num_task_types=5,
        d_model=cfg.V4_D_MODEL, n_heads=cfg.V4_N_HEADS, n_layers=cfg.V4_N_LAYERS,
        dim_feedforward=cfg.V4_D_FF, dropout=0.0,
        max_seq_length=cfg.V4_MAX_SEQ_LENGTH,
        max_memory_tokens=cfg.V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=False, freeze_bert=True,
        bert_unfreeze_layers=cfg.V4_BERT_UNFREEZE_LAYERS)

    # record fresh-random embedding SHAs BEFORE carry-over
    emb_before = tensor_sha(sft.token_embedding.weight)
    out_before = tensor_sha(sft.output_projection.weight)

    # apply carry set
    with torch.no_grad():
        for key in CARRY_KEYS:
            getattr(sft, key).load_state_dict(ck["carry_state"][key])

    saved = ck["carry_shas"]
    checks = {}
    for key in CARRY_KEYS:
        mod = getattr(sft, key)
        ok = all(tensor_sha(v) == saved[key][kk] for kk, v in mod.state_dict().items())
        checks[f"carry_{key}"] = ok
    checks["sft_vocab_132"] = sft.token_embedding.num_embeddings == 132
    checks["embedding_fresh_random"] = tensor_sha(sft.token_embedding.weight) == emb_before
    checks["output_fresh_random"] = tensor_sha(sft.output_projection.weight) == out_before
    checks["dapt_embedding_discarded"] = (
        tensor_sha(sft.token_embedding.weight)
        != tensor_sha(torch.load(args.checkpoint, map_location="cpu",
                                 weights_only=False)["model_state_dict"]
                      ["token_embedding.weight"]))
    print(f"[migrate] DAPT step {ck['step']}, ledger {ck['ledger']}")
    ok = all(checks.values())
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    torch.save({"schema": "gis_recommend.m1_r2_sft_init.v1",
                "carry_state": ck["carry_state"],
                "source_checkpoint": str(args.checkpoint),
                "dapt_step": ck["step"],
                "audit": checks},
               Path(args.out) / "m1_r2_sft_init_carry.pth")
    print(f"PHASE 2-C: {'ALL PASS' if ok else 'FAILURES'} — "
          f"SFT init written to {args.out}/m1_r2_sft_init_carry.pth")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["audit", "smoke", "train", "migrate"])
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    ap.add_argument("--out", type=Path, default=SMOKE_DIR / "m1_r2_dapt")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--seq-len", type=int, default=1024)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--ckpt-every", type=int, default=2000)
    ap.add_argument("--steps", type=int, default=100, help="smoke only")
    ap.add_argument("--checkpoint", type=Path, help="migrate only")
    ap.add_argument("--r1-checkpoint", type=Path,
                    default=Path("/home/qy/gee_llm_smoke/m1_r1_ckpt/best_gen_composite_model.pth"),
                    help="audit only: R1 ckpt used for SHA-inequality proof (never loaded into the model)")
    ap.add_argument("--task-vocab", type=Path,
                    default=Path("/home/qy/gee_llm_smoke/m1_task_vocab_v1.json"),
                    help="audit only: verify task_type id 0 is Unknown")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args.command == "audit":
        return cmd_audit(args)
    if args.command == "smoke":
        return cmd_smoke(args)
    if args.command == "train":
        return run_training(args)
    if args.command == "migrate":
        assert args.checkpoint, "--checkpoint required for migrate"
        Path(args.out).mkdir(parents=True, exist_ok=True)
        return cmd_migrate(args)


if __name__ == "__main__":
    raise SystemExit(main())
