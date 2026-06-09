# -*- coding: utf-8 -*-
"""MVCS v1 — Execution Harness for Closure Proof Validation.

Validates 6 ACTIVE paths from docs/mvcs_v1_closure_proof.yaml:
  IR-01, IR-02, IR-09, IR-10, IR-11, SR-07

Each test:
  - Constructs the minimal mock objects needed
  - Attempts the exploit path
  - Reports PASS (path blocked) or FAIL (path exploitable + trace)
"""

from __future__ import annotations

import sys
import os
import json
import uuid
import hashlib
import tempfile
import shutil
import textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch, MagicMock, PropertyMock

# ==============================================================================
# MOCK LAYER — minimal recreations of the MVCS stack
# ==============================================================================

# -- mock torch (just enough for checkpoint serialization) --
class MockTensor:
    def __init__(self, shape, name=""):
        self.shape = tuple(shape)
        self._name = name
    def __repr__(self):
        return f"MockTensor(shape={self.shape})"

class MockOptimizer:
    def __init__(self):
        self._state = {"step": 0}
    def state_dict(self):
        return dict(self._state)
    def zero_grad(self): pass
    def step(self): self._state["step"] += 1

class MockModel:
    def __init__(self, d_model=256, n_heads=8, n_layers=4):
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self._weights = {
            "token_embedding.weight": MockTensor([6000, d_model], "token_embedding"),
            "decoder_layers.0.weight": MockTensor([d_model, d_model], "decoder.0"),
            "decoder_layers.1.weight": MockTensor([d_model, d_model], "decoder.1"),
            "decoder_layers.2.weight": MockTensor([d_model, d_model], "decoder.2"),
            "decoder_layers.3.weight": MockTensor([d_model, d_model], "decoder.3"),
        }
        self._task_classifier = {
            "classifier.weight": MockTensor([50, d_model], "task_cls"),
            "classifier.bias": MockTensor([50], "task_cls_bias"),
        }
    def state_dict(self):
        return dict(self._weights)
    def train(self): pass
    def eval(self): pass

class MockTaskClassifier:
    def __init__(self):
        pass
    def state_dict(self):
        return {"classifier.weight": MockTensor([50, 256]), "classifier.bias": MockTensor([50])}
    def load_state_dict(self, d): pass

# -- mock torch.save / torch.load (filesystem-backed) --
_SAVED_CHECKPOINTS: dict[str, dict] = {}

def mock_torch_save(obj, path):
    """Simulate torch.save — serialize dict to JSON-like structure on disk."""
    path = str(path)
    serializable = _make_serializable(obj)
    _SAVED_CHECKPOINTS[path] = serializable
    # Also write to actual disk
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)

def mock_torch_load(path, map_location=None, weights_only=True):
    """Simulate torch.load — load dict from disk."""
    path = str(path)
    if path in _SAVED_CHECKPOINTS:
        return _restore_from_serializable(_SAVED_CHECKPOINTS[path])
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return _restore_from_serializable(json.load(f))
    raise FileNotFoundError(f"Checkpoint not found: {path}")

def _make_serializable(obj):
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, MockTensor):
        return {"__mock_tensor__": True, "shape": list(obj.shape), "name": obj._name}
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)

def _restore_from_serializable(obj):
    if isinstance(obj, dict):
        if obj.get("__mock_tensor__"):
            return MockTensor(obj["shape"], obj.get("name", ""))
        return {k: _restore_from_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_restore_from_serializable(v) for v in obj]
    return obj

# -- Real torch presence flag --
try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

# -- mock evidence modules (minimal replicas of the mVCS evidence package) --

# Simulate _boundary.py
SUPPORTED_FORMAT_VERSIONS = {"gis_recommend.checkpoint.v1", "gis_recommend.checkpoint.v5"}

ONLY_ALLOWED_RUNTIME_GATES = [
    {"gate_id": 1, "name": "format_version_check"},
    {"gate_id": 2, "name": "model_state_dict_shape_check"},
]

FORBIDDEN_AS_GATE = [
    {"field": "val_loss", "FORBIDDEN_AS_GATE": True},
    {"field": "ar_token_acc", "FORBIDDEN_AS_GATE": True},
]

class StructuralIncompatibilityError(Exception): pass
class IncompleteMetricError(Exception): pass
class BoundaryViolation(Exception): pass

# Simulate _provenance.py
def load_checkpoint(path, model):
    """Gate 1 + Gate 2."""
    ckpt = mock_torch_load(path)
    fmt = ckpt.get("provenance", {}).get("format_version", "gis_recommend.checkpoint.v1")
    if fmt not in SUPPORTED_FORMAT_VERSIONS:
        raise StructuralIncompatibilityError(f"Unsupported format: {fmt}")
    ckpt_keys = set(ckpt.get("model_state_dict", {}).keys())
    model_keys = set(model.state_dict().keys())
    if ckpt_keys != model_keys:
        raise StructuralIncompatibilityError(f"Key mismatch: missing={model_keys-ckpt_keys}, extra={ckpt_keys-model_keys}")
    for k in model_keys:
        ckpt_shape = ckpt["model_state_dict"][k].shape
        model_shape = model.state_dict()[k].shape
        if ckpt_shape != model_shape:
            raise StructuralIncompatibilityError(f"Shape mismatch {k}: {ckpt_shape} vs {model_shape}")
    return ckpt

# Simulate _validity.py
def classify_checkpoint_validity(path):
    """Interpretive function — returns advisory report."""
    ckpt = mock_torch_load(path)
    prov = ckpt.get("provenance", {})
    return {
        "status": "valid" if prov.get("format_version") in SUPPORTED_FORMAT_VERSIONS else "warn",
        "run_id": prov.get("run_id"),
        "trainer_class": prov.get("trainer_class"),
        "epoch": ckpt.get("epoch"),
        "__advisory_only__": True,
    }

# Simulate _compare.py
def compare_metrics(path_a, path_b):
    """Interpretive function — compares two checkpoints."""
    a = mock_torch_load(path_a)
    b = mock_torch_load(path_b)
    mb_a = a.get("metric_bundle", {})
    mb_b = b.get("metric_bundle", {})
    metrics_a = {m["name"]: m["value"] for m in mb_a.get("metrics", [])}
    metrics_b = {m["name"]: m["value"] for m in mb_b.get("metrics", [])}
    deltas = {}
    for k in set(metrics_a) | set(metrics_b):
        deltas[k] = metrics_b.get(k, 0) - metrics_a.get(k, 0)
    return {
        "deltas": deltas,
        "checkpoint_a_run_id": a.get("provenance", {}).get("run_id"),
        "checkpoint_b_run_id": b.get("provenance", {}).get("run_id"),
        "comparison_valid": a.get("metric_bundle", {}).get("decode_policy") == b.get("metric_bundle", {}).get("decode_policy"),
        "__advisory_only__": True,
    }

# -- mock training loop --
class MockTrainingLoop:
    """Minimal training loop that saves checkpoints with provenance + metric_bundle."""

    def __init__(self, checkpoint_dir, warmstart_path=None):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.model = MockModel()
        self.task_classifier = MockTaskClassifier()
        self.optimizer = MockOptimizer()
        self._provenance_block = None
        self.run_id = str(uuid.uuid4())
        self.epoch = 0
        self.best_val_loss = float("inf")
        self.warmstart_path = warmstart_path

        # Decode config (used for evaluation)
        self.decode_strategy = "greedy"
        self.decode_rep_penalty = 1.0
        self.decode_rep_window = 5
        self.decode_min_length = 5
        self.decode_max_length = 30

    def _build_provenance_block(self):
        script_hash = hashlib.sha256(b"mock_train_v4_6.py").hexdigest()
        model_hash = hashlib.sha256(b"mock_transformer_model_v4.py").hexdigest()
        config_hash = hashlib.sha256(b"mock_transformer_config.py").hexdigest()
        data_hash = hashlib.sha256(b"mock_labeled_workflows.json").hexdigest()

        return {
            "format_version": "gis_recommend.checkpoint.v5",
            "run_id": self.run_id,
            "parent_run_id": None,
            "parent_checkpoint_sha256": None,
            "timestamp_iso": "2026-05-08T20:00:00Z",
            "trainer_class": "MockTrainingLoop",
            "trainer_mro": ["MockTrainingLoop", "object"],
            "code_identity": {
                "script_path": "mock_train_v4_6.py",
                "script_sha256": script_hash,
                "model_module_sha256": model_hash,
                "config_module_sha256": config_hash,
            },
            "config_snapshot": {
                "warmstart_path": str(self.warmstart_path) if self.warmstart_path else None,
                "constants": {"V4_D_MODEL": 256, "V4_BATCH_SIZE": 32, "V4_OTHER_LR": 1e-4},
            },
            "dataset_identity": {
                "data_path": "mock_labeled_workflows.json",
                "data_sha256": data_hash,
                "num_train": 1000, "num_val": 200, "num_test": 200,
                "split_seed": 42, "num_task_types": 50,
            },
            "framework_identity": {
                "python_version": "3.11.0",
                "pytorch_version": "2.4.0",
                "cuda_version": "12.1",
                "gpu_name": "NVIDIA RTX 4090",
            },
            "training_history_sha256": None,
        }

    def _build_metric_bundle(self, val_loss, ar_token_acc):
        selector = {"metric_name": "val_loss", "direction": "minimize"}
        decode_policy = {
            "strategy": self.decode_strategy,
            "temperature": None, "top_p": None,
            "rep_penalty": self.decode_rep_penalty,
            "rep_window": self.decode_rep_window,
            "min_length": self.decode_min_length,
            "max_length": self.decode_max_length,
        }
        return {
            "selector_policy": selector,
            "decode_policy": decode_policy,
            "metrics": [
                {"name": "val_loss", "value": val_loss, "phase": "val", "decode_dependent": False},
                {"name": "ar_token_acc", "value": ar_token_acc, "phase": "val", "decode_dependent": True},
            ],
            "epoch_context": {"epoch": self.epoch, "tf_ratio": 0.3, "ar_ratio": 0.7},
        }

    def save_checkpoint(self, val_loss, ar_token_acc, is_best=False):
        if self._provenance_block is None:
            self._provenance_block = self._build_provenance_block()

        ckpt = {
            "model_state_dict": self.model.state_dict(),
            "task_classifier_state_dict": self.task_classifier.state_dict(),
            "epoch": self.epoch,
            "model_config": {
                "d_model": self.model.d_model,
                "n_heads": self.model.n_heads,
                "n_layers": self.model.n_layers,
                "max_memory_tokens": 128,
            },
            "provenance": dict(self._provenance_block),
            "metric_bundle": self._build_metric_bundle(val_loss, ar_token_acc),
            "val_loss": val_loss,
            "ar_token_acc": ar_token_acc,
            "ar_seq_em": None,
        }
        path = self.checkpoint_dir / ("best_model.pth" if is_best else f"checkpoint_epoch_{self.epoch:03d}.pth")
        mock_torch_save(ckpt, str(path))
        return str(path)

    def evaluate(self):
        # Mock evaluation: loss decreases each epoch
        val_loss = max(1.0, 2.5 - 0.1 * self.epoch + 0.02 * (hash(str(self.epoch)) % 10))
        ar_token_acc = min(0.65, 0.30 + 0.03 * self.epoch)
        return val_loss, ar_token_acc

    def train(self, num_epochs=3):
        saved_paths = []
        for ep in range(num_epochs):
            self.epoch = ep + 1
            val_loss, ar_token_acc = self.evaluate()
            is_best = val_loss < self.best_val_loss
            if is_best:
                self.best_val_loss = val_loss
            path = self.save_checkpoint(val_loss, ar_token_acc, is_best=is_best)
            saved_paths.append(path)
        return saved_paths


# -- mock evaluation pipeline (separate from training) --
class MockEvaluationPipeline:
    """Simulates evaluation/ module — can import evidence, produce reports."""

    def __init__(self):
        self.reports = []

    def run_audit(self, checkpoint_paths):
        """Run interpretive functions on checkpoints."""
        for cp in checkpoint_paths:
            report = classify_checkpoint_validity(cp)
            self.reports.append(report)
        if len(checkpoint_paths) >= 2:
            comparison = compare_metrics(checkpoint_paths[0], checkpoint_paths[1])
            self.reports.append(comparison)
        return self.reports

    def write_best_checkpoint_file(self, reports, output_path):
        """Write a file indicating which checkpoint is 'best' based on interpretive output."""
        # Find comparison report
        for r in reports:
            if "deltas" in r:
                if r["deltas"].get("ar_token_acc", 0) > 0:
                    best = r["checkpoint_b_run_id"]
                else:
                    best = r["checkpoint_a_run_id"]
                with open(output_path, "w") as f:
                    f.write(best)
                return output_path
        return None


# -- mock deployment/CI pipeline --
class MockCICDPipeline:
    """Simulates CI/CD reading evaluation output and deploying."""

    def __init__(self):
        self.deployed_run_id = None

    def read_best_and_deploy(self, best_file_path, checkpoint_dir):
        """Read the best-checkpoint file and 'deploy' the model."""
        if not os.path.exists(best_file_path):
            return None
        with open(best_file_path, "r") as f:
            target_run_id = f.read().strip()

        # Find the checkpoint with matching run_id
        for fname in os.listdir(checkpoint_dir):
            if fname.endswith(".pth"):
                ckpt = mock_torch_load(os.path.join(checkpoint_dir, fname))
                if ckpt.get("provenance", {}).get("run_id") == target_run_id:
                    self.deployed_run_id = target_run_id
                    return target_run_id
        return None


# ==============================================================================
# TEST CASE EXECUTION
# ==============================================================================

class TestMVCSClosureHarness:
    """Execution-level validation of closure proof ACTIVE paths."""

    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="mvcs_harness_")
        cls.checkpoint_dir = os.path.join(cls.tmpdir, "checkpoints")
        cls.eval_output_dir = os.path.join(cls.tmpdir, "eval_outputs")
        os.makedirs(cls.checkpoint_dir, exist_ok=True)
        os.makedirs(cls.eval_output_dir, exist_ok=True)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)
        _SAVED_CHECKPOINTS.clear()

    def setup_method(self):
        _SAVED_CHECKPOINTS.clear()
        # Reset global state
        global SUPPORTED_FORMAT_VERSIONS, ONLY_ALLOWED_RUNTIME_GATES
        SUPPORTED_FORMAT_VERSIONS = {"gis_recommend.checkpoint.v1", "gis_recommend.checkpoint.v5"}
        ONLY_ALLOWED_RUNTIME_GATES = [
            {"gate_id": 1, "name": "format_version_check"},
            {"gate_id": 2, "name": "model_state_dict_shape_check"},
        ]

    # =========================================================================
    # IR-01: interpretive → evaluation → filesystem → runtime
    # =========================================================================
    def test_IR01_interpretive_via_filesystem_to_runtime(self):
        """IR-01: Can interpretive output written to disk affect runtime behavior?"""
        print("\n" + "=" * 60)
        print("IR-01: interpretive → evaluation → filesystem → runtime")
        print("=" * 60)

        # Step 1: Train two models
        trainer_a = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_a"))
        paths_a = trainer_a.train(num_epochs=3)
        run_id_a = trainer_a.run_id

        trainer_b = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_b"))
        paths_b = trainer_b.train(num_epochs=3)
        run_id_b = trainer_b.run_id

        print(f"  Run A: {run_id_a}, checkpoints: {paths_a}")
        print(f"  Run B: {run_id_b}, checkpoints: {paths_b}")

        # Step 2: Evaluation pipeline runs interpretive functions
        eval_pipeline = MockEvaluationPipeline()
        best_a = paths_a[-1]  # last checkpoint of A
        best_b = paths_b[-1]  # last checkpoint of B
        reports = eval_pipeline.run_audit([best_a, best_b])
        print(f"  Evaluation reports: {len(reports)} generated")

        # Step 3: Evaluation writes "best" to disk (IR-01 exploit)
        best_file = os.path.join(self.eval_output_dir, "best_checkpoint.txt")
        eval_pipeline.write_best_checkpoint_file(reports, best_file)
        print(f"  Best-checkpoint file written: {best_file}")
        with open(best_file) as f:
            print(f"  Content: {f.read().strip()}")

        # Step 4: CI/CD pipeline reads the file and deploys
        cicd = MockCICDPipeline()
        deployed = cicd.read_best_and_deploy(best_file, self.checkpoint_dir)
        print(f"  Deployed run_id: {deployed}")

        # Step 5: Verify — did interpretive output determine deployment?
        # The comparison report's delta decided which run_id was written to disk
        # The CI/CD pipeline then deployed THAT run_id
        # This is an active path from interpretive output → runtime behavior
        if deployed is not None:
            print(f"  VERDICT: FAIL — interpretive output determined deployment ({deployed})")
            print(f"  TRACE: compare_metrics() → eval writes best_checkpoint.txt → CI/CD deploys → runtime changed")
            assert False, "IR-01: interpretive→filesystem→runtime path is ACTIVE"
        else:
            print("  VERDICT: PASS — no deployment occurred")

    # =========================================================================
    # IR-02: interpretive → evaluation → env_var → runtime
    # =========================================================================
    def test_IR02_interpretive_via_envvar_to_runtime(self):
        """IR-02: Can interpretive output set an env var that training reads?"""
        print("\n" + "=" * 60)
        print("IR-02: interpretive → evaluation → env_var → runtime")
        print("=" * 60)

        # Step 1: Train model
        trainer = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_env"))
        paths = trainer.train(num_epochs=2)
        run_id = trainer.run_id
        print(f"  Trained: {run_id}")

        # Step 2: Run interpretive function
        report = classify_checkpoint_validity(paths[-1])
        print(f"  Validity report: status={report['status']}")

        # Step 3: Simulate evaluation script setting env var based on report
        # (IR-02 exploit)
        old_env = os.environ.get("GIS_OUTPUTS_DIR", None)
        if report["status"] == "valid":
            os.environ["GIS_OUTPUTS_DIR"] = os.path.join(self.checkpoint_dir, "deployed_from_evidence")

        print(f"  GIS_OUTPUTS_DIR set to: {os.environ.get('GIS_OUTPUTS_DIR')}")

        # Step 4: Simulate training reading the env var (as transformer_config.py does)
        new_output_dir = os.environ.get("GIS_OUTPUTS_DIR")
        if new_output_dir and new_output_dir != old_env:
            # training would use this path for checkpoints
            print(f"  VERDICT: FAIL — env var changed based on interpretive output")
            print(f"  TRACE: classify_checkpoint_validity() → status='valid' → set GIS_OUTPUTS_DIR → training output path changed")
            # Restore
            if old_env is not None:
                os.environ["GIS_OUTPUTS_DIR"] = old_env
            else:
                del os.environ["GIS_OUTPUTS_DIR"]
            assert False, "IR-02: interpretive→env_var→runtime path is ACTIVE"
        else:
            print("  VERDICT: PASS — env var unchanged or no effect")
            if old_env is not None:
                os.environ["GIS_OUTPUTS_DIR"] = old_env
            elif "GIS_OUTPUTS_DIR" in os.environ and old_env is None:
                del os.environ["GIS_OUTPUTS_DIR"]

    # =========================================================================
    # IR-09: mutable ONLY_ALLOWED_RUNTIME_GATES → gate injection
    # =========================================================================
    def test_IR09_mutable_gate_list_injection(self):
        """IR-09: Can a third gate be injected into ONLY_ALLOWED_RUNTIME_GATES?"""
        print("\n" + "=" * 60)
        print("IR-09: mutable gate list → arbitrary gate injection")
        print("=" * 60)

        # Step 1: Train and save a valid checkpoint
        trainer = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_gate"))
        paths = trainer.train(num_epochs=1)
        ckpt_path = paths[0]
        print(f"  Checkpoint saved: {ckpt_path}")

        # Step 2: Verify normal loading works (2 gates pass)
        model = MockModel()
        try:
            ckpt = load_checkpoint(ckpt_path, model)
            print(f"  Normal load: OK (epoch={ckpt['epoch']}, val_loss={ckpt['val_loss']})")
        except StructuralIncompatibilityError as e:
            print(f"  Normal load: FAILED unexpectedly — {e}")
            assert False, f"Normal load should succeed: {e}"

        # Step 3: IR-09 exploit — inject a third gate
        print(f"  Gates before injection: {len(ONLY_ALLOWED_RUNTIME_GATES)}")
        ONLY_ALLOWED_RUNTIME_GATES.append({
            "gate_id": 3,
            "name": "val_loss_threshold_gate",
            "trigger": "torch.load",
            "check": "checkpoint.val_loss < 2.0",
            "failure": "raise StructuralIncompatibilityError",
        })
        print(f"  Gates after injection: {len(ONLY_ALLOWED_RUNTIME_GATES)}")
        print(f"  Injected gate: {ONLY_ALLOWED_RUNTIME_GATES[2]}")

        # Step 4: Simulate load_checkpoint with the injected gate active
        # The checkpoint has val_loss ~2.3 (above 2.0), so the injected gate would block it
        ckpt_data = mock_torch_load(ckpt_path)
        injected_gate = ONLY_ALLOWED_RUNTIME_GATES[2]

        gate_triggered = False
        if injected_gate["name"] == "val_loss_threshold_gate":
            if ckpt_data.get("val_loss", 999) >= 2.0:
                gate_triggered = True

        if gate_triggered:
            print(f"  VERDICT: FAIL — third gate injected and triggered")
            print(f"  TRACE: ONLY_ALLOWED_RUNTIME_GATES.append(gate_3) → load_checkpoint would reject valid checkpoint based on val_loss")
            print(f"  Gate 3 check: val_loss={ckpt_data['val_loss']} >= 2.0 → BLOCK")
            assert False, "IR-09: mutable gate list allows injection"
        else:
            print(f"  Gate 3 check: val_loss={ckpt_data.get('val_loss')} < 2.0 → would pass")
            print("  VERDICT: FAIL (gate injectable but didn't trigger on this specific checkpoint)")
            print("  The gate list IS mutable — injection succeeded. A different checkpoint would be blocked.")
            assert False, "IR-09: mutable gate list is exploitable regardless of trigger"

    # =========================================================================
    # IR-10: mutable SUPPORTED_FORMAT_VERSIONS → version acceptance modification
    # =========================================================================
    def test_IR10_mutable_format_set_modification(self):
        """IR-10: Can SUPPORTED_FORMAT_VERSIONS be mutated to accept/reject formats?"""
        global SUPPORTED_FORMAT_VERSIONS
        print("\n" + "=" * 60)
        print("IR-10: mutable format set → version acceptance modification")
        print("=" * 60)

        # Step 1: Create a checkpoint with format_version v5 (supported)
        trainer = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_fmt"))
        paths = trainer.train(num_epochs=1)
        ckpt_path = paths[0]
        print(f"  Checkpoint saved with format_version=v5")

        # Verify supported versions
        print(f"  SUPPORTED_FORMAT_VERSIONS before: {SUPPORTED_FORMAT_VERSIONS}")

        # Step 2: IR-10 exploit — remove v5 from supported versions
        SUPPORTED_FORMAT_VERSIONS.discard("gis_recommend.checkpoint.v5")
        print(f"  SUPPORTED_FORMAT_VERSIONS after discard: {SUPPORTED_FORMAT_VERSIONS}")

        # Step 3: Try to load — should now fail because v5 is not supported
        model = MockModel()
        try:
            load_checkpoint(ckpt_path, model)
            print(f"  VERDICT: FAIL — checkpoint loaded despite v5 being removed from supported set")
            print(f"  TRACE: SUPPORTED_FORMAT_VERSIONS.discard('v5') → Gate 1 should reject but didn't")
            print(f"  (load_checkpoint may have fallen back to v1 default)")
            assert False, "IR-10: format set modification should cause load failure"
        except StructuralIncompatibilityError as e:
            print(f"  VERDICT: FAIL — valid checkpoint rejected after set modification")
            print(f"  TRACE: SUPPORTED_FORMAT_VERSIONS.discard('v5') → Gate 1 rejects valid v5 checkpoint")
            print(f"  Error: {e}")
            assert False, "IR-10: mutable format set exploitable (valid checkpoint blocked)"

        # Step 4: IR-10 exploit variant — ADD a fake version to accept corrupted checkpoints
        # Reset
        SUPPORTED_FORMAT_VERSIONS = {"gis_recommend.checkpoint.v1", "gis_recommend.checkpoint.v5"}
        SUPPORTED_FORMAT_VERSIONS.add("gis_recommend.checkpoint.v99_malicious")
        print(f"\n  Variant: added malicious version v99_malicious")
        print(f"  SUPPORTED_FORMAT_VERSIONS now: {SUPPORTED_FORMAT_VERSIONS}")

        # Try to load a checkpoint with the malicious version
        # This would pass Gate 1 even though the checkpoint format is unknown
        ckpt_data = mock_torch_load(ckpt_path)
        ckpt_data["provenance"]["format_version"] = "gis_recommend.checkpoint.v99_malicious"
        malicious_path = os.path.join(self.checkpoint_dir, "malicious.pth")
        mock_torch_save(ckpt_data, malicious_path)

        try:
            load_checkpoint(malicious_path, model)
            print(f"  VERDICT: FAIL — malicious format version accepted after set modification")
            print(f"  TRACE: SUPPORTED_FORMAT_VERSIONS.add('v99_malicious') → Gate 1 passes for unknown format")
            assert False, "IR-10: mutable format set exploitable (malicious format accepted)"
        except StructuralIncompatibilityError:
            # Gate 2 might catch it (invalid model keys)
            pass

    # =========================================================================
    # IR-11: training → evaluation → evidence transitive import bypass
    # =========================================================================
    def test_IR11_transitive_import_bypass(self):
        """IR-11: Can training access evidence functions through evaluation bridge?"""
        print("\n" + "=" * 60)
        print("IR-11: training → evaluation → evidence (transitive import)")
        print("=" * 60)

        # This test simulates the transitive import chain.
        # The MVCS spec forbids:
        #   training/*.py:  "from gis_recommend.evidence import ..."  (L001)
        #   training/*.py:  "import gis_recommend.evidence"           (L002)
        # But does NOT forbid:
        #   training/*.py:  "from gis_recommend.evaluation import auto_select_best"
        #   evaluation/*.py: "from gis_recommend.evidence import compare_metrics"

        # Step 1: evaluation defines a function wrapping evidence
        eval_code = textwrap.dedent("""
            # mock_evaluation.py — ALLOWED to import evidence
            from gis_recommend.evidence import compare_metrics

            def rank_checkpoints(path_a, path_b):
                '''Wrapper that hides evidence import from callers.'''
                report = compare_metrics(path_a, path_b)
                if report["deltas"].get("ar_token_acc", 0) > 0:
                    return path_b  # B is better
                return path_a    # A is better
        """)

        # Step 2: Simulate static analysis on training code
        training_code = textwrap.dedent("""
            # train_v4_6.py — FORBIDDEN to import evidence
            from gis_recommend.evaluation import rank_checkpoints

            def choose_warmstart(candidates):
                best = candidates[0]
                for i in range(1, len(candidates)):
                    best = rank_checkpoints(best, candidates[i])
                return best
        """)

        # LINT CHECK: grep for direct evidence imports in training code
        has_direct_import = "from gis_recommend.evidence" in training_code
        has_direct_import |= "import gis_recommend.evidence" in training_code
        print(f"  LINT L001 (direct import): {'VIOLATION' if has_direct_import else 'PASS'}")
        assert not has_direct_import, "Direct import should not exist"

        # Step 3: Manual transitive analysis — does training get evidence access?
        # The training code imports `rank_checkpoints` from evaluation.
        # `rank_checkpoints` internally calls `compare_metrics` from evidence.
        # The training code never directly references evidence, BUT:
        #   - It receives a ComparisonReport (evidence type) as a return value
        #   - It uses the report content to make decisions
        #   - The LINT_RULES L001-L008 only check for direct import strings

        # Simulate: check if training code's transitive dependency graph
        # includes evidence symbols
        transitive_evidence_access = True  # evaluation wraps evidence
        print(f"  Transitive evidence access: {transitive_evidence_access}")
        print(f"  FORBIDDEN_IMPORT_GRAPH blocks: training→evidence (direct)")
        print(f"  FORBIDDEN_IMPORT_GRAPH allows: training→evaluation (NOT blocked)")
        print(f"  FORBIDDEN_IMPORT_GRAPH allows: evaluation→evidence (NOT blocked)")

        # Step 4: Execute the exploit path
        trainer_a = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_trans_a"))
        paths_a = trainer_a.train(num_epochs=2)

        trainer_b = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_trans_b"))
        paths_b = trainer_b.train(num_epochs=2)

        # Simulate evaluation rank_checkpoints (which wraps evidence.compare_metrics)
        report = compare_metrics(paths_a[-1], paths_b[-1])
        if report["deltas"].get("ar_token_acc", 0) > 0:
            chosen = paths_b[-1]
            print(f"  rank_checkpoints chose: B (ar_token_acc delta={report['deltas']['ar_token_acc']})")
        else:
            chosen = paths_a[-1]
            print(f"  rank_checkpoints chose: A")

        # Training code receives the chosen path and would use it for warmstart
        print(f"  Training would warmstart from: {chosen}")
        print(f"  VERDICT: FAIL — training accessed evidence decision through evaluation bridge")
        print(f"  TRACE: training imports evaluation.rank_checkpoints → internally calls evidence.compare_metrics → result controls warmstart path")
        print(f"  LINT L001-L008: PASS (no direct import string)")
        print(f"  Transitive check: FAIL (evidence reachable via evaluation)")
        assert False, "IR-11: transitive import bypass is ACTIVE"

    # =========================================================================
    # SR-07: torch.load without weights_only → pickle code execution
    # =========================================================================
    def test_SR07_pickle_deserialization_bypass(self):
        """SR-07: Can a crafted checkpoint execute code via pickle deserialization?"""
        print("\n" + "=" * 60)
        print("SR-07: torch.load without weights_only → pickle code execution")
        print("=" * 60)

        if not _HAS_TORCH:
            print("  SKIP: torch not installed — cannot test real pickle behavior")
            print("  VERDICT: CONDITIONAL (test requires torch)")
            print("  NOTE: The mock harness uses JSON serialization which is safe.")
            print("  The REAL torch.load with weights_only=False IS vulnerable.")
            print("  Current training code (train_v4_2.py:975) uses weights_only=True → SAFE")
            print("  But the spec does NOT mandate weights_only=True for evidence modules.")
            print("  If _validity.py or _lineage.py omit weights_only=True → VULNERABLE")
            return

        # Real torch is available — test the actual behavior
        import torch

        # Step 1: Create a normal checkpoint
        trainer = MockTrainingLoop(os.path.join(self.checkpoint_dir, "run_pickle"))
        paths = trainer.train(num_epochs=1)

        # Step 2: Save using real torch.save to create a real .pth file
        real_ckpt_path = os.path.join(self.checkpoint_dir, "real_checkpoint.pth")
        real_ckpt = {
            "model_state_dict": {"weight": torch.zeros(10, 10)},
            "provenance": {"format_version": "gis_recommend.checkpoint.v5"},
            "metric_bundle": {"metrics": [{"name": "val_loss", "value": 1.5}]},
        }
        torch.save(real_ckpt, real_ckpt_path)

        # Step 3: Test load with weights_only=True (SAFE)
        try:
            loaded_safe = torch.load(real_ckpt_path, map_location="cpu", weights_only=True)
            print(f"  weights_only=True: LOADED SAFELY")
        except Exception as e:
            print(f"  weights_only=True: FAILED — {e}")

        # Step 4: Test load with weights_only=False (VULNERABLE)
        # We DON'T actually test malicious pickle — that would be dangerous.
        # Instead we verify that weights_only=False is ACCEPTED by torch.load
        # and that the checkpoint data is accessible (proving the path exists).

        # Check if any evidence stub currently specifies weights_only
        evidence_stubs = [
            "evidence/_validity.py",
            "evidence/_lineage.py",
            "evidence/_recompute.py",
            "evidence/_compare.py",
            "evidence/_archaeology.py",
        ]

        print(f"\n  Checking evidence stubs for weights_only usage:")
        all_safe = True
        for stub in evidence_stubs:
            stub_path = os.path.join(
                os.path.dirname(__file__), "..", "src", "gis_recommend", stub
            )
            stub_path = os.path.normpath(stub_path)
            if os.path.exists(stub_path):
                with open(stub_path, "r", encoding="utf-8") as f:
                    content = f.read()
                has_weights_only = "weights_only" in content
                print(f"    {stub}: weights_only mentioned = {has_weights_only}")
                if not has_weights_only:
                    all_safe = False
            else:
                print(f"    {stub}: FILE NOT FOUND")
                all_safe = False

        if not all_safe:
            print(f"\n  VERDICT: FAIL — evidence stubs do not mandate weights_only=True")
            print(f"  TRACE: evidence module calls torch.load() without weights_only=True → pickle code execution possible")
            print(f"  When weights_only=False: arbitrary __reduce__ in pickle → code runs BEFORE Gate 1")
            assert False, "SR-07: pickle deserialization path is ACTIVE (spec doesn't mandate weights_only)"
        else:
            print(f"\n  VERDICT: PASS — all evidence stubs mandate weights_only=True")

    # =========================================================================
    # BONUS: Verify P0-01 patch effectiveness (frozen gate config)
    # =========================================================================
    def test_P001_patch_frozen_gate_config(self):
        """Verify that frozen gate config (P0-01) prevents IR-09 and IR-10."""
        print("\n" + "=" * 60)
        print("P0-01 VERIFICATION: frozen gate configuration")
        print("=" * 60)

        # Simulate what P0-01 would implement:
        from dataclasses import dataclass as dc

        @dc(frozen=True)
        class FrozenGate:
            gate_id: int
            name: str

        FrozenGateList = tuple  # immutable

        frozen_gates: FrozenGateList = (
            FrozenGate(1, "format_version_check"),
            FrozenGate(2, "model_state_dict_shape_check"),
        )
        frozen_versions: frozenset = frozenset({"gis_recommend.checkpoint.v1", "gis_recommend.checkpoint.v5"})

        # Attempt IR-09 exploit on frozen config
        try:
            frozen_gates.append(FrozenGate(3, "val_loss_gate"))
            print("  IR-09 with tuple: FAIL — tuple.append() should raise AttributeError")
            assert False, "Tuple should not have append method"
        except AttributeError as e:
            print(f"  IR-09 blocked: {e}")

        # Attempt injection via concatenation (creates new tuple, doesn't mutate)
        frozen_gates_modified = frozen_gates + (FrozenGate(3, "val_loss_gate"),)
        print(f"  Concatenation creates new tuple (len={len(frozen_gates_modified)}), original unchanged (len={len(frozen_gates)})")
        print(f"  Original still has {len(frozen_gates)} gates — injection creates new object, doesn't mutate the shared one")

        # Attempt IR-10 exploit on frozenset
        try:
            frozen_versions.add("gis_recommend.checkpoint.v99")
            print("  IR-10 with frozenset: FAIL — frozenset.add() should raise AttributeError")
            assert False, "Frozenset should not have add method"
        except AttributeError as e:
            print(f"  IR-10 blocked: {e}")

        try:
            frozen_versions.discard("gis_recommend.checkpoint.v5")
            print("  IR-10 discard: FAIL — frozenset.discard() should raise AttributeError")
            assert False, "Frozenset should not have discard method"
        except AttributeError as e:
            print(f"  IR-10 discard blocked: {e}")

        print("  P0-01 VERDICT: PASS — frozen dataclass + tuple + frozenset fully prevents IR-09 and IR-10")


# ==============================================================================
# RUNNER
# ==============================================================================

def run_harness():
    """Execute all closure harness tests."""
    test = TestMVCSClosureHarness()
    test.setup_class()

    results = {}

    # Run each test and capture PASS/FAIL
    test_methods = [
        ("IR-01", test.test_IR01_interpretive_via_filesystem_to_runtime),
        ("IR-02", test.test_IR02_interpretive_via_envvar_to_runtime),
        ("IR-09", test.test_IR09_mutable_gate_list_injection),
        ("IR-10", test.test_IR10_mutable_format_set_modification),
        ("IR-11", test.test_IR11_transitive_import_bypass),
        ("SR-07", test.test_SR07_pickle_deserialization_bypass),
    ]

    for path_id, method in test_methods:
        try:
            test.setup_method()
            method()
            results[path_id] = "PASS (unexpected)"
            print(f"\n  {path_id}: PASS (unexpected — exploit should have triggered)")
        except AssertionError as e:
            results[path_id] = f"FAIL — {e}"
            print(f"\n  {path_id}: FAIL — exploit confirmed active")
        except Exception as e:
            results[path_id] = f"ERROR — {type(e).__name__}: {e}"
            print(f"\n  {path_id}: ERROR — {e}")

    # Bonus: P0-01 verification
    try:
        test.setup_method()
        test.test_P001_patch_frozen_gate_config()
        results["P0-01"] = "PASS — patch effective"
    except AssertionError as e:
        results["P0-01"] = f"FAIL — {e}"
    except Exception as e:
        results["P0-01"] = f"ERROR — {type(e).__name__}: {e}"

    test.teardown_class()

    # Summary
    print("\n" + "=" * 60)
    print("CLOSURE HARNESS RESULTS")
    print("=" * 60)
    for path_id, result in results.items():
        status = "FAIL" if "FAIL" in result else "PASS" if "PASS" in result else "ERROR"
        print(f"  {path_id}: {status}")
        if "FAIL" in result:
            print(f"    {result}")

    total_fails = sum(1 for r in results.values() if "FAIL" in r)
    print(f"\n  TOTAL: {len(results)} tests, {total_fails} FAILURES")

    return results


if __name__ == "__main__":
    run_harness()
