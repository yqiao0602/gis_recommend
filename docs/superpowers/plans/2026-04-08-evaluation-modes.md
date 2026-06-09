# Evaluation Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fixed `smoke/dev/full` evaluation modes so routine experiments run on stable stratified subsets instead of the full 11K test set by default.

**Architecture:** Extend `scripts/evaluate_system.py` with a deterministic evaluation-mode resolver and a stronger stratified sampler that allocates per-task-type quotas proportionally while preserving broad task coverage. Keep `--samples` as an explicit override so one-off experiments still work.

**Tech Stack:** Python, `argparse`, `unittest`

---

### Task 1: Add Failing Tests For Evaluation Mode Resolution

**Files:**
- Create: `tests/test_evaluate_system_sampling.py`
- Test: `tests/test_evaluate_system_sampling.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_resolve_eval_max_samples_uses_mode_defaults():
    ...

def test_resolve_eval_max_samples_prefers_explicit_samples():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_evaluate_system_sampling -v`
Expected: FAIL because the resolver helper does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
EVAL_MODE_MAX_SAMPLES = {"smoke": 200, "dev": 1000, "full": None}

def resolve_eval_max_samples(eval_mode, explicit_samples):
    if explicit_samples is not None:
        return explicit_samples
    return EVAL_MODE_MAX_SAMPLES[eval_mode]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_evaluate_system_sampling -v`
Expected: PASS

### Task 2: Add Failing Tests For Deterministic Stratified Sampling

**Files:**
- Modify: `tests/test_evaluate_system_sampling.py`
- Test: `tests/test_evaluate_system_sampling.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_test_set_allocates_samples_across_task_types():
    ...

def test_build_test_set_is_deterministic_for_same_seed():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_evaluate_system_sampling -v`
Expected: FAIL because the current sampler does not implement the new quota-based behavior.

- [ ] **Step 3: Write minimal implementation**

```python
def allocate_stratified_quotas(by_type, max_samples):
    ...

def build_test_set(...):
    effective_max_samples = resolve_eval_max_samples(...)
    quotas = allocate_stratified_quotas(...)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_evaluate_system_sampling -v`
Expected: PASS

### Task 3: Wire CLI And Report Metadata

**Files:**
- Modify: `scripts/evaluate_system.py`
- Test: `tests/test_evaluate_system_sampling.py`

- [ ] **Step 1: Add CLI option and defaults**

```python
parser.add_argument(
    "--eval-mode",
    choices=["smoke", "dev", "full"],
    default="dev",
)
```

- [ ] **Step 2: Record effective evaluation settings in metadata**

```python
report["experiment_meta"]["eval_mode"] = args.eval_mode
report["experiment_meta"]["effective_max_samples"] = effective_max_samples
```

- [ ] **Step 3: Run targeted tests**

Run: `python -m unittest tests.test_evaluate_system_sampling tests.test_reranker_evaluate_system -v`
Expected: PASS

- [ ] **Step 4: Run syntax verification**

Run: `python -m py_compile scripts/evaluate_system.py`
Expected: exit code 0
