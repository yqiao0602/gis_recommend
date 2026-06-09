# L3 Inference Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize L3 sequence inference to produce shorter, cleaner sequences by adjusting parameters, adding early stopping, post-processing, and dynamic expected length.

**Architecture:** Only inference-time changes — no retraining. Modify `_apply_constraints()` for consecutive dedup + END boost, add early stopping in beam search + temperature sampling, add post-processing before scoring, and load per-task-type length stats.

**Tech Stack:** Python, PyTorch (inference only), JSON stats file.

**Spec:** `docs/superpowers/specs/2026-03-14-l3-inference-optimization-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/gis_recommend/config/transformer_config.py` | Modify | Score weight constants |
| `src/gis_recommend/inference/infer_l3_candidates_v4.py` | Modify | max_length, consecutive dedup, END boost, early stopping, post-processing, dynamic expected_length |
| `src/gis_recommend/pipelines/interactive_system.py` | Modify | One-line call to set_expected_length |
| `scripts/compute_task_type_length_stats.py` | Create | Pre-compute per-task-type length stats |
| `outputs/task_type_length_stats.json` | Generate | Stats cache |

---

## Task 0: Capture Baseline

Before making any changes, record current behavior for A/B comparison.

- [ ] **Step 1: Run 5 test cases and save baseline**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python << 'PYEOF'
import sys, json
sys.path.insert(0, 'src')
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem

system = InteractiveQGISSystem()
queries = [
    "Calculate terrain slope from DEM and classify slope categories",
    "Create buffer zones around rivers and intersect with buildings",
    "Calculate NDVI from satellite imagery and classify vegetation health",
    "Merge multiple vector layers and dissolve by attribute field",
    "Reproject raster data from WGS84 to UTM and clip to study area boundary",
]
baseline = []
for q in queries:
    r = system.process_user_query(q)
    if r['success']:
        baseline.append({
            "query": q,
            "l3_sequence": r["l3_sequence"],
            "l3_length": len(r["l3_sequence"]),
            "qgis_chain": r["qgis_chain"],
            "qgis_length": len(r["qgis_chain"]),
            "unknown_count": r["unknown_count"],
        })
system.close()

with open("outputs/baseline_before_l3_optimization.json", "w", encoding="utf-8") as f:
    json.dump(baseline, f, ensure_ascii=False, indent=2)

print("\n=== BASELINE SAVED ===")
for b in baseline:
    print(f"\n{b['query'][:50]}...")
    print(f"  L3 length: {b['l3_length']}, QGIS length: {b['qgis_length']}, Unknown: {b['unknown_count']}")
    print(f"  L3: {' -> '.join(b['l3_sequence'][:5])}...")
PYEOF
```

---

## Task 1: Adjust Score Weights

**Files:**
- Modify: `src/gis_recommend/config/transformer_config.py:186-190`

- [ ] **Step 1: Change the 4 weight constants**

Replace lines 186-190:

```python
# V4 Candidate Scoring Weights
V4_SCORE_LOG_PROB_WEIGHT = 0.25    # was 0.4 — reduce pure probability dominance
V4_SCORE_TRANSITION_WEIGHT = 0.30  # unchanged
V4_SCORE_LENGTH_WEIGHT = 0.35     # was 0.2 — make length penalty competitive
V4_SCORE_DIVERSITY_WEIGHT = 0.10  # unchanged
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "import sys; sys.path.insert(0,'src'); from gis_recommend.config.transformer_config import V4_SCORE_LOG_PROB_WEIGHT, V4_SCORE_LENGTH_WEIGHT; print(f'log_prob={V4_SCORE_LOG_PROB_WEIGHT}, length={V4_SCORE_LENGTH_WEIGHT}')"
```
Expected: `log_prob=0.25, length=0.35`

---

## Task 2: Change max_length and Add Consecutive Dedup

**Files:**
- Modify: `src/gis_recommend/inference/infer_l3_candidates_v4.py:105` (max_length default)
- Modify: `src/gis_recommend/inference/infer_l3_candidates_v4.py:245-274` (_apply_constraints)

- [ ] **Step 1: Change max_length default from 50 to 25**

Line 105, change:
```python
        max_length: int = 25,
```

- [ ] **Step 2: Add consecutive dedup and END boost to `_apply_constraints()`**

After the transition constraint block (after line 273 `logits[b] += mask`), before `return logits` (line 274), add:

```python
            # Consecutive token dedup: block same token as last generated
            # Placed after transition constraints; absolute assignment overrides additive mask
            if gen and len(gen) > 0:
                last_token = gen[-1]
                if last_token < logits.size(1):
                    logits[b, last_token] = float('-inf')

        # END token progressive boost: encourage stopping after expected_length
        if step > self.expected_length:
            overshoot = step - self.expected_length
            bonus = 0.5 * overshoot
            logits[:, END_INDEX] += bonus

        return logits
```

Note: remove the existing `return logits` at line 274 since it's now included above.

- [ ] **Step 3: Verify syntax**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -c "import sys; sys.path.insert(0,'src'); import ast; ast.parse(open('src/gis_recommend/inference/infer_l3_candidates_v4.py', encoding='utf-8').read()); print('OK')"
```
Expected: `OK`

---

## Task 3: Add Early Stopping to Beam Search and Temperature Sampling

**Files:**
- Modify: `src/gis_recommend/inference/infer_l3_candidates_v4.py:299-302` (diverse_beam_search beam expansion)
- Modify: `src/gis_recommend/inference/infer_l3_candidates_v4.py:393` (temperature_sample inner loop)

- [ ] **Step 1: Add per-beam cutoff in `diverse_beam_search()`**

After the `if finished:` block (line 300-301), before the tensor building (line 304), add a new length check:

```python
                for beam_idx, (tokens, lp, finished) in enumerate(group_beams):
                    if finished:
                        group_cands.append((tokens, lp, True))
                        continue

                    # Per-beam length cutoff
                    if len(tokens) - 1 > self.expected_length * 1.8:
                        group_cands.append((tokens, lp, True))
                        continue

                    # Build input tensors for this beam
```

- [ ] **Step 2: Add early stop in `temperature_sample()`**

In the temperature_sample inner loop (line 393), after `for step in range(1, self.max_length):`, add at the top of the loop body:

```python
            for step in range(1, self.max_length):
                # Early stop if past expected length cutoff
                if step > self.expected_length * 1.8:
                    break

                seq = torch.tensor([tokens], dtype=torch.long, device=self.device)
```

- [ ] **Step 3: Add completion penalty in `_score_and_rank()`**

After the `c.final_score = (...)` assignment (line 495), add:

```python
            # Penalize incomplete sequences (did not generate END)
            if not c.is_complete:
                c.final_score *= 0.8
```

- [ ] **Step 4: Verify syntax**

```bash
python -c "import sys; sys.path.insert(0,'src'); import ast; ast.parse(open('src/gis_recommend/inference/infer_l3_candidates_v4.py', encoding='utf-8').read()); print('OK')"
```
Expected: `OK`

---

## Task 4: Add Post-processing

**Files:**
- Modify: `src/gis_recommend/inference/infer_l3_candidates_v4.py` — add method + call in infer/infer_from_model_input

- [ ] **Step 1: Add `_postprocess_sequence()` method**

Add after `_compute_diversity_score()` (around line 470), before `_score_and_rank()`:

```python
    def _postprocess_sequence(self, tokens: List[int]) -> List[int]:
        """Remove consecutive duplicates and tail loops from generated tokens."""
        if not tokens:
            return tokens

        # 1. Remove consecutive duplicates
        deduped = [tokens[0]]
        for t in tokens[1:]:
            if t != deduped[-1]:
                deduped.append(t)

        # 2. Truncate tail loops: if 3+ consecutive tokens at the end
        #    are all previously-seen, cut the repeated tail
        if len(deduped) > 4:
            seen = set()
            repeat_streak = 0
            cut_point = len(deduped)
            for i, t in enumerate(deduped):
                if t in seen:
                    repeat_streak += 1
                    if repeat_streak >= 3:
                        cut_point = i - 2
                        break
                else:
                    repeat_streak = 0
                seen.add(t)
            deduped = deduped[:cut_point]

        return deduped
```

- [ ] **Step 2: Call post-processing in `infer_from_model_input()`**

In `infer_from_model_input()`, before `return self._score_and_rank(candidates)` (line 565), add:

```python
        # Post-process sequences before scoring
        for c in candidates:
            c.tokens = self._postprocess_sequence(c.tokens)
            c.length = len(c.tokens)

        return self._score_and_rank(candidates)
```

- [ ] **Step 3: Call post-processing in `infer()`**

Find the `infer()` method's equivalent `return self._score_and_rank(candidates)` line and add the same block before it.

- [ ] **Step 4: Verify syntax**

```bash
python -c "import sys; sys.path.insert(0,'src'); import ast; ast.parse(open('src/gis_recommend/inference/infer_l3_candidates_v4.py', encoding='utf-8').read()); print('OK')"
```
Expected: `OK`

---

## Task 5: Dynamic expected_length

**Files:**
- Create: `scripts/compute_task_type_length_stats.py`
- Modify: `src/gis_recommend/inference/infer_l3_candidates_v4.py` — add `set_expected_length()` + load stats at init
- Modify: `src/gis_recommend/pipelines/interactive_system.py:347` — one-line call

- [ ] **Step 1: Create the stats computation script**

```python
"""
compute_task_type_length_stats.py

Pre-compute per-task-type L3 sequence length statistics from training data.
Output: outputs/task_type_length_stats.json
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_PATH = PROJECT_ROOT / "outputs" / "labeled_workflows_l3_v4_cleaned.json"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "task_type_length_stats.json"


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    workflows = data["labeled_workflows"]
    print(f"[OK] Loaded {len(workflows)} workflows")

    type_lengths = defaultdict(list)
    all_lengths = []

    for w in workflows:
        seq = w.get("l3_sequence", [])
        length = len(seq)
        all_lengths.append(length)

        task_meta = w.get("task_metadata", {})
        task_type = task_meta.get("task_type", "Unknown")
        type_lengths[task_type].append(length)

    # Compute global stats
    all_lengths.sort()
    n = len(all_lengths)
    global_stats = {
        "mean": round(sum(all_lengths) / n, 1),
        "median": int(statistics.median(all_lengths)),
        "p90": all_lengths[int(n * 0.9)],
    }

    # Compute per-type stats
    type_stats = {}
    for task_type, lens in sorted(type_lengths.items()):
        if len(lens) < 5:
            continue
        lens.sort()
        m = len(lens)
        type_stats[task_type] = {
            "count": m,
            "mean": round(sum(lens) / m, 1),
            "median": int(statistics.median(lens)),
            "p90": lens[int(m * 0.9)],
        }

    output = {
        "global": global_stats,
        "by_task_type": type_stats,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Saved to {OUTPUT_PATH}")
    print(f"  Global: median={global_stats['median']}, mean={global_stats['mean']}, p90={global_stats['p90']}")
    print(f"  Task types: {len(type_stats)}")
    for tt, s in list(type_stats.items())[:5]:
        print(f"    {tt}: n={s['count']}, median={s['median']}, mean={s['mean']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script to generate stats**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python scripts/compute_task_type_length_stats.py
```

Expected: Generates `outputs/task_type_length_stats.json` with global and per-type stats.

- [ ] **Step 3: Add `set_expected_length()` and stats loading to the inferencer**

In `infer_l3_candidates_v4.py`, add to `__init__()` after `self.expected_length = 12` (line 127):

```python
        self.expected_length = 12
        self._length_stats = self._load_length_stats()
```

Add the two new methods after `__init__()`:

```python
    def _load_length_stats(self) -> dict:
        """Load pre-computed per-task-type length stats."""
        from gis_recommend.config.transformer_config import OUTPUT_DIR
        path = OUTPUT_DIR / "task_type_length_stats.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  [OK] Length stats loaded ({len(data.get('by_task_type', {}))} task types)")
            return data
        print(f"  [INFO] No length stats file found, using default expected_length=12")
        return {}

    def set_expected_length(self, task_type: str):
        """Set expected_length based on task type. Falls back to global median or 12."""
        if not self._length_stats:
            return
        by_type = self._length_stats.get("by_task_type", {})
        if task_type in by_type:
            self.expected_length = by_type[task_type]["median"]
        else:
            global_stats = self._length_stats.get("global", {})
            self.expected_length = global_stats.get("median", 12)
```

- [ ] **Step 4: Call `set_expected_length()` from `_generate_l3_sequences()`**

In `src/gis_recommend/pipelines/interactive_system.py`, in `_generate_l3_sequences()`, add before the `if model_input:` check (line 348):

```python
        try:
            # Set dynamic expected length based on task type
            if hasattr(self.l3_inferencer, 'set_expected_length'):
                self.l3_inferencer.set_expected_length(task_type)

            # 使用L3SequenceInferencer的infer方法
            if model_input:
```

- [ ] **Step 5: Verify syntax for both files**

```bash
python -c "import sys; sys.path.insert(0,'src'); import ast; ast.parse(open('src/gis_recommend/inference/infer_l3_candidates_v4.py', encoding='utf-8').read()); print('infer OK')"
python -c "import sys; sys.path.insert(0,'src'); import ast; ast.parse(open('src/gis_recommend/pipelines/interactive_system.py', encoding='utf-8').read()); print('system OK')"
```
Expected: Both print `OK`

---

## Task 6: End-to-end Verification

- [ ] **Step 1: Run the same 5 test cases**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python << 'PYEOF'
import sys, json
sys.path.insert(0, 'src')
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem

system = InteractiveQGISSystem()
queries = [
    "Calculate terrain slope from DEM and classify slope categories",
    "Create buffer zones around rivers and intersect with buildings",
    "Calculate NDVI from satellite imagery and classify vegetation health",
    "Merge multiple vector layers and dissolve by attribute field",
    "Reproject raster data from WGS84 to UTM and clip to study area boundary",
]
after = []
for q in queries:
    r = system.process_user_query(q)
    if r['success']:
        after.append({
            "query": q,
            "l3_sequence": r["l3_sequence"],
            "l3_length": len(r["l3_sequence"]),
            "qgis_chain": r["qgis_chain"],
            "qgis_length": len(r["qgis_chain"]),
            "unknown_count": r["unknown_count"],
        })
system.close()

# Compare with baseline
with open("outputs/baseline_before_l3_optimization.json", "r", encoding="utf-8") as f:
    baseline = json.load(f)

print("\n" + "="*70)
print("A/B COMPARISON: BEFORE vs AFTER L3 INFERENCE OPTIMIZATION")
print("="*70)
for b, a in zip(baseline, after):
    print(f"\nQuery: {b['query'][:60]}...")
    print(f"  L3 length:   {b['l3_length']:>3} -> {a['l3_length']:>3}  {'IMPROVED' if a['l3_length'] < b['l3_length'] else 'SAME' if a['l3_length'] == b['l3_length'] else 'WORSE'}")
    print(f"  QGIS length: {b['qgis_length']:>3} -> {a['qgis_length']:>3}")
    print(f"  Unknown:     {b['unknown_count']:>3} -> {a['unknown_count']:>3}")
    # Check for consecutive duplicates
    has_consec = any(a['l3_sequence'][i] == a['l3_sequence'][i+1] for i in range(len(a['l3_sequence'])-1))
    print(f"  Consecutive dupes: {'YES (BAD)' if has_consec else 'No'}")
    print(f"  L3: {' -> '.join(a['l3_sequence'][:6])}{'...' if len(a['l3_sequence']) > 6 else ''}")

avg_before = sum(b['l3_length'] for b in baseline) / len(baseline)
avg_after = sum(a['l3_length'] for a in after) / len(after)
print(f"\nAverage L3 length: {avg_before:.1f} -> {avg_after:.1f}")
PYEOF
```

Expected:
- Average L3 sequence length ≤ 10 (was ~9.8 but with many at 11+)
- No consecutive duplicate L3 codes
- Key L3 primitives still present
