# M1-R1 integration smoke: 10-item preflight checklist — PASSED

Run on the compute server, real paper_v1 data and the real V4.6 model. Two runs:
a 2-epoch TF smoke (640-row stratified subset for speed) and a 1-epoch AR-SS
smoke via warm-start from the TF checkpoint. The frozen-protocol sampler was
verified active in both (`[M1-R1] platform sampler: GEE 70% / QGIS 30%`).

| # | Check | Result |
|---|---|---|
| 1 | 7-key batch contract complete | PASS — trainer consumed batches; keys input_ids/target_ids/task_type_id/text_input_ids/text_attention_mask/attention_mask/sample_weight |
| 2 | 276 steps/epoch (8,832 samples) | PASS — sampler reports samples/epoch=8,832 on the full train set (unit-tested); smoke subset 640/32 = 20 steps |
| 3 | metadata does not pollute batch | PASS — batch dict contains only the 7 contract keys |
| 4 | forward | PASS — TF loss computed (epoch1 15.68 → epoch2 9.31) |
| 5 | backward | PASS — parameters updated, loss decreasing |
| 6 | gradients finite | PASS — no NaN/Inf; losses finite across both phases |
| 7 | TF phase | PASS — 2 epochs TF, train loss 15.68 → 9.31, val 20.23 → 16.87 |
| 8 | AR-SS produces autoregressive samples | PASS — `[AR-SS] Starting autoregressive scheduled sampling`, AR-SS(tf=0.42, ar=50%), AR-SeqEM / AR-TokenAcc / AR-LCS / AR-SetF1 all computed |
| 9 | EOS mask does not produce inf | PASS — all AR/TF losses finite |
| 10 | checkpoint save/reload | PASS — latest/best/best_gen_{set_f1,lcs,composite} saved; warm-start reload of best_model.pth succeeded |

## Blocking issues found and fixed during the smoke

1. **Server had a stale quality-gate script.** `/home/qy/system_redesign/scripts/
   train_v4_6_quality_gate.py` was the 2026-07-08 copy (SHA `8fd79782…`) with no
   M1-R1 trainer hook — the first smoke silently ran the *default* sampler.
   Backed up as `train_v4_6_quality_gate.py.predates_m1r1_20260708`; deployed the
   hooked version (SHA `0e9ebf1f…`, = server version + trainer override +
   `--transition-matrix` support, the latter inert unless passed).
2. **Vocabulary profile mismatch.** paper_v1's L3 vocabulary is the frozen
   128-token taxonomy (max token 124), while every existing V4 profile is
   94/107/124 — the run fails closed under `v2_94_stable`. Built and registered
   the isolated **`paper_v1_128`** profile: id_mappings for 128 codes from the
   taxonomy authority, embeddings 128×256 (rows 0-93 reused verbatim, 94-127
   seeded `128256`), task vocabulary (5 types), length stats and transition
   table from paper_v1 train, manifest with all input/output hashes. Registered
   in `vocab_profile.py` **and** in `transformer_config.py`'s env switch (the
   latter was missing and caused the first failure). Production `v2_94_stable`
   and the stable124 experiment are untouched.

## Preflight finding for the user (not a blocker)

`ar_max_steps = 20` but paper_v1 train has **323 rows (3.66%) with more than 20
L3 steps** (max 97, p99 41; 319 GEE + 4 QGIS). The AR phase truncates those.
Options: raise `ar_max_steps` for M1-R1, or accept that 96.3% of rows are fully
covered and report the truncation. All rows are within the 100-token V4 limit.

---

# Addendum: ar_max_steps=40 capacity smoke — PASSED (2026-09-09, user decision (a))

CLI support added (`--ar-max-steps`, default unchanged at 20; one threading bug
where the new parameter duplicated an existing one was caught by compileall and
fixed). Smoke re-run warm-started with `--ar-max-steps 40`:

| Check | Result |
|---|---|
| AR-SS forward/backward at horizon 40 | PASS — 40 steps ran, exit 0 |
| Memory | 6.8 GB GPU (no growth vs horizon 20) |
| Loss finite | PASS — all TF/AR losses finite |
| 40-step horizon operational | PASS — `ar_max_steps: 40` reported |
| EOS mask | PASS — no inf |
| Checkpoint | PASS — saved |

Speed: ~2.1 s/step on the 640-row smoke (vs ~1.5 s at horizon 20) — AR rollout
cost roughly proportional to horizon, as expected.

**Coverage at horizon 40: 98.98%** of train rows (90 rows >40 steps remain; they
are the extreme 50–97-step chains). Per the user's decision this replaces the
96.34% coverage at horizon 20; the remaining 1.02% is accepted rather than
raising the horizon to 100.

## M1-R1 final frozen protocol (all decisions locked)

| Item | Value |
|---|---|
| Data | paper_v1: train 8,817 / val frozen 49 / test untouched |
| Sampler | platform 70:30; GEE first-L3 family 37-way; QGIS chain-length 4-way |
| Sampling | replacement=True; batch 32; 8,832 samples/epoch; 276 steps/epoch |
| Vocabulary | paper_v1_128 (128 content tokens; production 94 / stable124 untouched) |
| Training | TF 10 epochs → AR-SS progressive; **ar_max_steps=40** |
| Architecture | V4.6 unchanged |
| Eval | development/diagnostic 49 rows, same format as M3-P1-EOS-R1 |

Gate for a run to count as M1-R1: script SHA + trainer SHA + sampler SHA +
profile SHA pinned, and the log must contain
`[M1-R1] platform sampler: GEE 70% / QGIS 30%`.
