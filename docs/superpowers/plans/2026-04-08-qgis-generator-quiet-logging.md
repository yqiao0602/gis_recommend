# QGIS Generator Quiet Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce evaluation log noise by making `QGISCandidateGenerator` quiet by default and showing progress at the evaluation loop level instead.

**Architecture:** Add a `verbose` switch to `QGISCandidateGenerator` and route detailed per-step prints through a guarded helper so default runs stay quiet. Replace reranker sample counter prints in `scripts/evaluate_system.py` with a `tqdm` progress bar so long-running evaluation still exposes progress without flooding the terminal.

**Tech Stack:** Python, `unittest`, `tqdm`

---

### Task 1: Add Regression Tests For Quiet Logging

**Files:**
- Create: `tests/test_qgis_candidate_generator_logging.py`
- Test: `tests/test_qgis_candidate_generator_logging.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_generate_candidates_quiet_by_default():
    ...

def test_generate_candidates_verbose_emits_step_logs():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_qgis_candidate_generator_logging -v`
Expected: FAIL because `QGISCandidateGenerator` does not yet support quiet/verbose log gating.

- [ ] **Step 3: Write minimal implementation**

```python
class QGISCandidateGenerator:
    def __init__(..., verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_qgis_candidate_generator_logging -v`
Expected: PASS

### Task 2: Replace Evaluation Counter Prints With Progress Bar

**Files:**
- Modify: `scripts/evaluate_system.py`
- Test: `tests/test_reranker_evaluate_system.py`

- [ ] **Step 1: Wire `tqdm` into the reranker loop**

```python
from tqdm import tqdm

for i, (sample, l3_res) in enumerate(tqdm(..., desc="Reranker", total=len(test_set))):
    ...
```

- [ ] **Step 2: Keep candidate generator quiet in evaluation**

```python
qgis_gen = QGISCandidateGenerator(..., verbose=False)
```

- [ ] **Step 3: Run targeted regression tests**

Run: `python -m unittest tests.test_reranker_evaluate_system tests.test_qgis_candidate_generator_logging -v`
Expected: PASS

- [ ] **Step 4: Run syntax verification**

Run: `python -m py_compile src/gis_recommend/operators/qgis_candidate_generator.py scripts/evaluate_system.py`
Expected: exit code 0
