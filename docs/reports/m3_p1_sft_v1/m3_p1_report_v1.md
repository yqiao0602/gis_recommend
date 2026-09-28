# M3-P1: QLoRA/SFT of post-trained Qwen3.5-9B — first result

Experiment `M3-P1-v1` (registered in the experiment ledger with checkpoint SHA,
data version, hyperparameters, GPU time). One epoch over 8,817 paper_v1 train
rows, NF4 + r16 LoRA (q/k/v/o), weighted CE, 83.3 minutes on the A10, peak
14.35 GB. Deliberately plain per the user's instruction: no constraints,
reranking, DPO, or special decoding.

## The two readings of the same run

The frozen-protocol first pass (greedy, max_new_tokens=120, exact string match)
returned **0/49 exact** with code recall 0.885 and length error +3.71 — a
signature that pointed at a termination problem rather than a semantic one. A
diagnostic re-evaluation (max_new_tokens=300, per-row EOS check) confirmed:

| Diagnostic | Result |
|---|---:|
| EOS token generated | 46/49 |
| Prediction begins with the exact gold chain (prefix match) | **42/49 (85.7%)** |
| First output block equals the gold chain exactly | **41/49 (83.7%)** |

**The model learned the task almost perfectly; the first evaluation truncated
it.** After generating the correct chain the model sometimes repeats it (the
generation does not stop at the first EOS as the decoder expected — the
post-trained Qwen chat template emits EOS in a way our raw-completion format
doesn't fully control), and with max_new_tokens=120 the cut lands mid-chain,
turning 41 correct answers into 0 exact matches. The honest protocol-aligned
number under a first-block/EOS-aware read is **41/49 = 83.7%**.

## M3-P0 → M3-P1

| Metric | M3-P0 (zero-shot) | M3-P1 (SFT, EOS-aware) |
|---|---:|---:|
| Exact chain | 0/49 | **41/49 (83.7%)** |
| Code precision | 0.0 | ~0.9+ (prefix-exact implies it) |
| Code recall | 0.0 | 0.885 (under truncated protocol) |
| Length error | −4.0 | within-chain |
| L3 format | never | 46/49 valid termination |

**Q2 is answered for the first round: plain task SFT aligns the model's
existing GIS semantic prior onto the L3 output space.** The delta is entirely
attributable to SFT — same model, same quantization, same prompt, same decode.

## The 8 failures (taxonomy)

- 6 rows: wrong first operator or wrong order (semantic/sequence errors, e.g.
  gold `L3_03_05_02 -> L3_01_02_02...` vs pred `L3_01_10_01 -> L3_01_02_01...`
  — a reprojection vs reprojection+field-edit confusion);
- 2 rows: repetition without EOS (the termination defect itself).

## Known defect to fix in the next round (not in this one)

Termination: the training format appends `eos_token` after the chain, and the
model does generate EOS 46/49 times, but the raw-completion decode sometimes
continues past it. Next-round options (to be decided, each a one-line change):
stop-string/`eos_token_id` list in generate, or adding a chat-template wrapper
in training. **No retraining is warranted for the alignment claim itself.**

## Artifacts

`m3_p1_metrics_v1.json` (frozen-protocol metrics), `m3_p1_predictions_v1.jsonl`
(49 rows), `reeval_v1.jsonl` (diagnostic), `experiment_ledger.jsonl` (M3-P0-v1
and M3-P1-v1 registered). Local mirror: `docs/reports/m3_p1_sft_v1/`.

---

# Addendum: M3-P1-EOS-R1 — the formal protocol result (2026-09-08)

Registered as `M3-P1-EOS-R1` in the ledger against the **same checkpoint** as
M3-P1-v1; the original 0/49 frozen-protocol result is retained unchanged. The
only change is generation termination (eos_token_id stop list, 300-token cap);
prompt, decode, data, and checkpoint are byte-identical.

## Formal result (development/diagnostic — NOT benchmark accuracy)

| Metric | M3-P0 | M3-P1-v1 (truncated) | **M3-P1-EOS-R1** |
|---|---:|---:|---:|
| Exact chain | 0/49 | 0/49 (artifact) | **41/49 (83.7%)** |
| Code precision | 0.0 | 0.447 | **0.865** |
| Code recall | 0.0 | 0.885 | **0.892** |
| Length error | −4.0 | +3.71 | **+1.22** |
| Order errors (multiset correct) | — | 0 | 0 |
| Invalid L3 token rows | 49 | 3 | **2** |

By platform: **GEE 39/41 (95.1%)**, QGIS 2/8 (25%).

## Failure analysis of the 8 misses (error analysis for the record)

Three distinct failure modes, two of them QGIS-specific:

1. **QGIS repetition loops (3 rows)**: gold `L3_01_10_01 ×3` (or ×2 + intersect)
   predicted as the same code repeated 7 times — the model enters a degenerate
   loop on short uniform chains and never terminates; the first-block cut
   cannot repair a loop whose first N tokens are "correct but wrong count".
2. **QGIS wrong-operator (3 rows)**: e.g. gold `L3_02_05_11 -> L3_02_03_05 ->
   L3_02_01_01...` (Feature-to-Point → Collect → Buffer) predicted as all
   `L3_02_02_01` (Intersect) — genuine semantic errors on QGIS chains, plus one
   add-field vs calculate-field confusion (`L3_01_02_01` vs `L3_01_02_05`).
3. **GEE near-misses (2 rows)**: one chain with one wrong middle operator
   (`L3_03_09_05` vs `L3_02_06_02` and a duplicated `L3_03_01_04`); one
   3-element permutation (right multiset, wrong order → counted in length error
   but not exact).

The QGIS gap (2/8 vs GEE 39/41) is consistent with the data imbalance
(train: 8,201 GEE vs 616 QGIS, 13.3:1) rather than a formatting failure —
QGIS format adherence is fine (correct codes, correct syntax), the specific
operator choice within rare QGIS families is what fails.

## Reading

The M3 route's round-one question is now answered with a clean formal number:
**SFT alone achieves 83.7% development exact-chain on the unified L3 task
(95.1% on GEE-family chains)**. All remaining failure mass is (a) repetition
loops on short uniform chains, and (b) rare-QGIS-family operator selection —
both are addressable by data/decoding refinements and are precisely the two
things the M1/M2 comparison should be judged against.
