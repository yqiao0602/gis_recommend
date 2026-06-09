# MVCS v1 — Machine-Verifiable Constraint System
# Target: gis_recommend checkpoint v5 compliance
# Generated from: Phase 15C.2 v5 FINAL Unified Contract
# Date: 2026-05-08

##############################################################################
# (A) RULE DSL
##############################################################################
# Syntax:
#   RULE <name>:
#     scope: <module_pattern>
#     trigger: <event>
#     enforce: <action>
#     error: <error_type>
#     check: <deterministic_predicate>
#   END

# ---- Structural Gating Rules (2 allowed) ----

RULE format_version_gate:
  scope: evidence._provenance.load_checkpoint
  trigger: torch.load(checkpoint_path)
  enforce: GATE_BLOCK
  error: StructuralIncompatibilityError
  check: >
    checkpoint.provenance.format_version IN
    {"gis_recommend.checkpoint.v1", "gis_recommend.checkpoint.v5"}
  gate_id: 1
END

RULE model_state_dict_shape_gate:
  scope: evidence._provenance.load_checkpoint
  trigger: after RULE format_version_gate passes
  enforce: GATE_BLOCK
  error: StructuralIncompatibilityError
  check: >
    SET(model.state_dict().keys()) == SET(checkpoint.model_state_dict.keys())
    AND
    FORALL k IN model.state_dict().keys():
      model.state_dict()[k].shape == checkpoint.model_state_dict[k].shape
  gate_id: 2
END

# ---- Provenance Integrity Rules ----

RULE provenance_must_exist_on_first_save:
  scope: training.*.save_checkpoint
  trigger: first torch.save(checkpoint_dict) per run
  enforce: REQUIRED_FIELD
  error: ProvenanceError
  check: >
    checkpoint_dict HAS_KEY "provenance"
    AND checkpoint_dict.provenance.format_version IS NOT NULL
    AND checkpoint_dict.provenance.run_id IS NOT NULL
END

RULE provenance_write_once:
  scope: training.*.save_checkpoint
  trigger: any torch.save after first save in same run
  enforce: IMMUTABLE
  error: ProvenanceIntegrityError
  check: >
    self._provenance_block EXISTS
    AND checkpoint_dict.provenance == self._provenance_block
  violation: >
    IF checkpoint_dict.provenance != self._provenance_block
    OR checkpoint_dict.provenance IS None
    OR checkpoint_dict.provenance.run_id != self._provenance_block.run_id
END

RULE run_id_unchanged_within_run:
  scope: training.*.save_checkpoint
  trigger: every torch.save
  enforce: INVARIANT
  error: ProvenanceIntegrityError
  check: >
    checkpoint_dict.provenance.run_id == self._provenance_block.run_id
END

RULE provenance_no_backfill:
  scope: evidence._provenance
  trigger: any write to checkpoint file
  enforce: FORBIDDEN
  error: ProvenanceViolation
  check: >
    NO code path writes provenance block to an existing .pth file
    after training completion
END

RULE provenance_parent_null_when_warmstart_missing:
  scope: training.*.__init__
  trigger: warmstart checkpoint not found at config_path
  enforce: REQUIRED_STATE
  check: >
    IF load_warmstart_checkpoint() returns None:
      checkpoint_dict.provenance.parent_run_id == null
      AND checkpoint_dict.provenance.parent_checkpoint_sha256 == null
      AND checkpoint_dict.provenance.config_snapshot.warmstart_path == config_path
END

# ---- Metric Bundle Integrity Rules ----

RULE metric_bundle_must_exist_on_save:
  scope: training.*.save_checkpoint
  trigger: every torch.save that includes metrics
  enforce: REQUIRED_FIELD
  error: IncompleteMetricError
  check: >
    checkpoint_dict HAS_KEY "metric_bundle"
END

RULE decode_policy_must_exist_when_decode_dependent_metrics_present:
  scope: training.*.save_checkpoint
  trigger: every torch.save
  enforce: REQUIRED_FIELD
  error: IncompleteMetricError
  check: >
    IF EXISTS m IN checkpoint_dict.metric_bundle.metrics
       WHERE m.decode_dependent == true:
      checkpoint_dict.metric_bundle.decode_policy IS NOT NULL
      AND checkpoint_dict.metric_bundle.decode_policy.strategy IS NOT NULL
      AND checkpoint_dict.metric_bundle.decode_policy.rep_penalty IS NOT NULL
      AND checkpoint_dict.metric_bundle.decode_policy.rep_window IS NOT NULL
      AND checkpoint_dict.metric_bundle.decode_policy.min_length IS NOT NULL
      AND checkpoint_dict.metric_bundle.decode_policy.max_length IS NOT NULL
END

RULE selector_policy_must_exist:
  scope: training.*.save_checkpoint
  trigger: every torch.save
  enforce: REQUIRED_FIELD
  error: IncompleteMetricError
  check: >
    checkpoint_dict.metric_bundle.selector_policy IS NOT NULL
    AND checkpoint_dict.metric_bundle.selector_policy.metric_name IS NOT NULL
    AND checkpoint_dict.metric_bundle.selector_policy.direction IN {"minimize", "maximize"}
END

# ---- Structural Boundary Rules ----

RULE no_evidence_import_in_training:
  scope: training/*
  trigger: static analysis
  enforce: FORBIDDEN
  error: BoundaryViolation
  check: >
    FORALL file IN training/*.py:
      "from gis_recommend.evidence" NOT IN file.content
      AND "import gis_recommend.evidence" NOT IN file.content
END

RULE no_evidence_import_in_inference:
  scope: inference/*
  trigger: static analysis
  enforce: FORBIDDEN
  error: BoundaryViolation
  check: >
    FORALL file IN inference/*.py:
      "from gis_recommend.evidence" NOT IN file.content
      AND "import gis_recommend.evidence" NOT IN file.content
END

RULE no_evidence_import_in_models:
  scope: models/*
  trigger: static analysis
  enforce: FORBIDDEN
  error: BoundaryViolation
  check: >
    FORALL file IN models/*.py:
      "from gis_recommend.evidence" NOT IN file.content
      AND "import gis_recommend.evidence" NOT IN file.content
END

RULE no_evidence_import_in_pipelines:
  scope: pipelines/*
  trigger: static analysis
  enforce: FORBIDDEN
  error: BoundaryViolation
  check: >
    FORALL file IN pipelines/*.py:
      "from gis_recommend.evidence" NOT IN file.content
      AND "import gis_recommend.evidence" NOT IN file.content
END

RULE evidence_module_only_reads_snapshot:
  scope: evidence/*
  trigger: static analysis
  enforce: REQUIRED
  error: BoundaryViolation
  check: >
    FORALL file IN evidence/*.py:
      NO torch.save() call in file.content
      AND NO model.train() call in file.content
      AND NO optimizer.step() call in file.content
      AND NO model.load_state_dict() call in file.content
      AND NO DataLoader(..., shuffle=True) in file.content
      AND NO loss.backward() call in file.content
END

# ---- Runtime Independence Rules ----

RULE no_runtime_access_to_metric_bundle:
  scope: training/*.train_epoch
  scope: training/*._train_step_ar
  scope: training/*._train_step_tf
  scope: training/*.validate
  scope: training/*.evaluate_generation
  trigger: runtime execution
  enforce: FORBIDDEN
  error: RuntimeDependencyViolation
  check: >
    FORALL method IN [train_epoch, _train_step_ar, _train_step_tf,
                      validate, evaluate_generation]:
      NO access to self._provenance_block
      AND NO access to checkpoint file on disk
      AND NO access to metric_bundle after it is built
END

RULE no_interpretive_output_controls_runtime:
  scope: training/*
  scope: inference/*
  scope: pipelines/*
  trigger: static analysis
  enforce: FORBIDDEN
  error: InterpretiveGateViolation
  check: >
    FORALL file IN [training, inference, pipelines]:
      NO string "classify_checkpoint_validity" in file.content
      AND NO string "reconstruct_lineage" in file.content
      AND NO string "recompute_metrics" in file.content
      AND NO string "compare_metrics" in file.content
      AND NO string "diff_dispatch" in file.content
      AND NO string "generate_archaeology_report" in file.content
      AND NO string "ValidityReport" in file.content
      AND NO string "ComparisonReport" in file.content
      AND NO string "LineageGraph" in file.content
      AND NO string "RecomputeReport" in file.content
      AND NO string "ArchaeologyReport" in file.content
END

# ---- Snapshot Immutability Rules ----

RULE snapshot_never_modified_after_save:
  scope: ALL
  trigger: any code path
  enforce: FORBIDDEN
  error: SnapshotModificationViolation
  check: >
    NO code path does:
      ckpt = torch.load(path)
      ckpt['provenance'] = modified_provenance
      torch.save(ckpt, path)  # overwrite
    AND NO code path does:
      ckpt = torch.load(path)
      ckpt['metric_bundle'] = modified_bundle
      torch.save(ckpt, path)
    AND NO code path does:
      ckpt = torch.load(path)
      ckpt['provenance'][any_key] = new_value
      torch.save(ckpt, path)
END

# ---- Code Identity Rules ----

RULE code_identity_sha256_must_be_file_hash:
  scope: training.*.build_provenance_block
  trigger: first save per run
  enforce: REQUIRED
  error: CodeIdentityError
  check: >
    provenance.code_identity.script_sha256 == sha256(__file__)
    AND provenance.code_identity.model_module_sha256 == sha256(transformer_model_v4.__file__)
    AND provenance.code_identity.config_module_sha256 == sha256(transformer_config.__file__)
END

RULE dataset_identity_sha256_must_be_data_hash:
  scope: training.*.build_provenance_block
  trigger: first save per run
  enforce: REQUIRED
  error: DatasetIdentityError
  check: >
    provenance.dataset_identity.data_sha256 == sha256(data_file_path)
END

##############################################################################
# (B) FORBIDDEN EDGE GRAPH
##############################################################################

# Direction: source -> target
# Mark: ALLOWED | FORBIDDEN | ONE_WAY

# Adjacency list of ALL cross-layer edges

EDGE_GRAPH = {

  # runtime -> runtime: ALLOWED
  ("runtime", "runtime"): "ALLOWED",

  # runtime -> snapshot: ONE_WAY (only via torch.save)
  ("runtime", "snapshot"): "ONE_WAY:torch_save",

  # runtime -> interpretive: ALLOWED (runtime has no awareness of interpretive)
  ("runtime", "interpretive"): "ALLOWED:no_dependency",

  # snapshot -> runtime: RESTRICTED (only model_state_dict key/shape)
  ("snapshot", "runtime"): "RESTRICTED:model_state_dict_only",

  # snapshot -> snapshot: FORBIDDEN (no cross-checkpoint mutation)
  ("snapshot", "snapshot"): "FORBIDDEN",

  # snapshot -> interpretive: ALLOWED (interpretive reads snapshot)
  ("snapshot", "interpretive"): "ALLOWED:read_only",

  # interpretive -> runtime: FORBIDDEN
  ("interpretive", "runtime"): "FORBIDDEN",

  # interpretive -> snapshot: FORBIDDEN (never writes)
  ("interpretive", "snapshot"): "FORBIDDEN",

  # interpretive -> interpretive: ALLOWED (composition)
  ("interpretive", "interpretive"): "ALLOWED:pure_composition",
}

# Forbidden imports adjacency list
FORBIDDEN_IMPORT_GRAPH = {
    "training":    ["evidence"],
    "inference":   ["evidence"],
    "models":      ["evidence"],
    "pipelines":   ["evidence"],
    "evidence":    [],           # evidence may import from anywhere else
}

# Forbidden method access adjacency list
FORBIDDEN_METHOD_GRAPH = {
    # (caller_module, callee_module) -> forbidden_methods[]
    ("training", "evidence"): [
        "classify_checkpoint_validity",
        "reconstruct_lineage",
        "recompute_metrics",
        "compare_metrics",
        "diff_dispatch",
        "generate_archaeology_report",
        "ValidityReport",
        "ComparisonReport",
        "LineageGraph",
        "RecomputeReport",
        "DispatchDiff",
        "ArchaeologyReport",
        "RecomputeContext",
    ],
    ("training", "checkpoint"): [
        # Training may not load a checkpoint and use its provenance/metric_bundle
        # for any decision other than structural loading
        "checkpoint['provenance']",    # outside of build_provenance_block()
        "checkpoint['metric_bundle']", # outside of build_metric_bundle()
        "checkpoint['parent_run_id']",
        "checkpoint['selector_policy']",
    ],
}

# Snapshot field -> runtime access
SNAPSHOT_RUNTIME_ACCESS = {
    "model_state_dict":             "ALLOWED:load_only",
    "task_classifier_state_dict":   "ALLOWED:load_only",
    "epoch":                        "ALLOWED:display_only",
    "model_config":                 "ALLOWED:display_only",
    "val_loss":                     "ALLOWED:display_only",
    "ar_token_acc":                 "ALLOWED:display_only",
    "ar_seq_em":                    "ALLOWED:display_only",
    "provenance":                   "FORBIDDEN:runtime_access",
    "metric_bundle":                "FORBIDDEN:runtime_access",
}

##############################################################################
# (C) VALIDATION CONTRACT — Gate System
##############################################################################

ONLY_ALLOWED_RUNTIME_GATES = [
    {
        "gate_id": 1,
        "name": "format_version_check",
        "trigger": "torch.load",
        "check": "checkpoint.provenance.format_version IN SUPPORTED_FORMATS",
        "failure": "raise StructuralIncompatibilityError",
        "scope": "structural_only",
    },
    {
        "gate_id": 2,
        "name": "model_state_dict_shape_check",
        "trigger": "after gate_1 passes",
        "check": "keys_match AND all_shapes_match",
        "failure": "raise StructuralIncompatibilityError",
        "scope": "structural_only",
    },
]

FORBIDDEN_AS_GATE = [
    # Every field EXCEPT those listed in ONLY_ALLOWED_RUNTIME_GATES
    {
        "field": "provenance.run_id",
        "FORBIDDEN_AS_GATE": true,
        "reason": "semantic identity, not structural",
    },
    {
        "field": "provenance.parent_run_id",
        "FORBIDDEN_AS_GATE": true,
        "reason": "lineage is informational",
    },
    {
        "field": "provenance.code_identity.*",
        "FORBIDDEN_AS_GATE": true,
        "reason": "code version is informational",
    },
    {
        "field": "provenance.config_snapshot.*",
        "FORBIDDEN_AS_GATE": true,
        "reason": "config is informational",
    },
    {
        "field": "provenance.dataset_identity.*",
        "FORBIDDEN_AS_GATE": true,
        "reason": "dataset identity is informational",
    },
    {
        "field": "provenance.framework_identity.*",
        "FORBIDDEN_AS_GATE": true,
        "reason": "framework is informational",
    },
    {
        "field": "metric_bundle.selector_policy",
        "FORBIDDEN_AS_GATE": true,
        "reason": "selector is historical record, not instruction",
    },
    {
        "field": "metric_bundle.decode_policy",
        "FORBIDDEN_AS_GATE": true,
        "reason": "decode policy is metric context, not runtime config",
    },
    {
        "field": "metric_bundle.metrics[*].value",
        "FORBIDDEN_AS_GATE": true,
        "reason": "metric values are archival, not evaluative",
    },
    {
        "field": "val_loss",
        "FORBIDDEN_AS_GATE": true,
        "reason": "metric is informational, not structural",
    },
    {
        "field": "ar_token_acc",
        "FORBIDDEN_AS_GATE": true,
        "reason": "metric is informational, not structural",
    },
    {
        "field": "ar_seq_em",
        "FORBIDDEN_AS_GATE": true,
        "reason": "metric is informational, not structural",
    },
    {
        "field": "epoch",
        "FORBIDDEN_AS_GATE": true,
        "reason": "epoch is informational, not structural",
    },
]

##############################################################################
# (D) SCHEMA → CONSTRAINT MAPPING
##############################################################################

# Every field in checkpoint_v5.pt mapped to its constraint profile
# type: structural | snapshot_evidence | legacy
# allowed_usage: gate_load | write_once | read_only | forbidden_in_runtime
# can_affect_runtime: true | false

SCHEMA_CONSTRAINT_MAP = {

    # === STRUCTURAL LAYER ===
    "model_state_dict": {
        "type": "structural",
        "allowed_usage": "gate_load",
        "can_affect_runtime": true,
        "gate_id": 2,
        "constraint": "keys AND shapes must match model architecture",
    },
    "task_classifier_state_dict": {
        "type": "structural",
        "allowed_usage": "gate_load",
        "can_affect_runtime": true,
        "gate_id": 2,
        "constraint": "if present, keys AND shapes must match task_classifier architecture",
    },
    "epoch": {
        "type": "legacy",
        "allowed_usage": "read_only",
        "can_affect_runtime": false,
        "constraint": "integer, display only, never gates",
    },
    "model_config": {
        "type": "legacy",
        "allowed_usage": "read_only",
        "can_affect_runtime": false,
        "constraint": "dict, display only, never gates",
    },

    # === EVIDENCE: PROVENANCE ===
    "provenance": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "entire block written once, never modified, never backfilled",
    },
    "provenance.format_version": {
        "type": "snapshot_evidence",
        "allowed_usage": "gate_load",
        "can_affect_runtime": true,
        "gate_id": 1,
        "constraint": "string, one of SUPPORTED_FORMATS, checked at load only",
    },
    "provenance.run_id": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "UUID4 string, opaque, invariant within run",
    },
    "provenance.parent_run_id": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "UUID4 string | null, records warm-start source identity",
    },
    "provenance.parent_checkpoint_sha256": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "hex string | null, sha256 of warm-start source .pth file",
    },
    "provenance.timestamp_iso": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "ISO 8601 UTC string, set at save time",
    },
    "provenance.trainer_class": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "fully-qualified class name string",
    },
    "provenance.trainer_mro": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "list of class name strings, top-to-bottom MRO order",
    },
    "provenance.code_identity": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict with 4 sha256 hex strings",
    },
    "provenance.code_identity.script_path": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "absolute path string of training script",
    },
    "provenance.code_identity.script_sha256": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "sha256 hex string of training .py file",
    },
    "provenance.code_identity.model_module_sha256": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "sha256 hex string of transformer_model_v4.py",
    },
    "provenance.code_identity.config_module_sha256": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "sha256 hex string of transformer_config.py",
    },
    "provenance.config_snapshot": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict with warmstart_path + constants dict",
    },
    "provenance.config_snapshot.warmstart_path": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "string | null, the config-level warm-start path at train start",
    },
    "provenance.config_snapshot.constants": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict of {name: JSON-serializable value} for all V4_* + key config names",
    },
    "provenance.dataset_identity": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict with data fingerprint fields",
    },
    "provenance.dataset_identity.data_path": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "absolute path string of labeled workflows JSON",
    },
    "provenance.dataset_identity.data_sha256": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "sha256 hex string of data file at train start",
    },
    "provenance.dataset_identity.num_train": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "integer",
    },
    "provenance.dataset_identity.num_val": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "integer",
    },
    "provenance.dataset_identity.num_test": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "integer",
    },
    "provenance.dataset_identity.split_seed": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "integer, the RANDOM_SEED used for train/val/test split",
    },
    "provenance.dataset_identity.num_task_types": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "integer, size of task type vocabulary",
    },
    "provenance.framework_identity": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict with python, pytorch, cuda, gpu version strings",
    },
    "provenance.framework_identity.python_version": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "sys.version string",
    },
    "provenance.framework_identity.pytorch_version": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "torch.__version__ string",
    },
    "provenance.framework_identity.cuda_version": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "torch.version.cuda string | null",
    },
    "provenance.framework_identity.gpu_name": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "torch.cuda.get_device_name(0) string | null",
    },
    "provenance.training_history_sha256": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "sha256 hex string | null, set at training completion",
    },

    # === EVIDENCE: METRIC BUNDLE ===
    "metric_bundle": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "entire block written at save time, never modified",
    },
    "metric_bundle.selector_policy": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict, records selection criterion, never replayed as instruction",
    },
    "metric_bundle.selector_policy.metric_name": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "string, one of known metric names",
    },
    "metric_bundle.selector_policy.direction": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "string, 'minimize' | 'maximize'",
    },
    "metric_bundle.decode_policy": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict, complete snapshot of decode config used for AR metric measurement",
    },
    "metric_bundle.decode_policy.strategy": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "string, 'greedy' | 'nucleus' | 'beam'",
    },
    "metric_bundle.decode_policy.temperature": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "float | null, null for greedy",
    },
    "metric_bundle.decode_policy.top_p": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "float | null, null for greedy",
    },
    "metric_bundle.decode_policy.rep_penalty": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "float, >= 0",
    },
    "metric_bundle.decode_policy.rep_window": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "int, >= 1",
    },
    "metric_bundle.decode_policy.min_length": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "int, >= 1",
    },
    "metric_bundle.decode_policy.max_length": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "int, model.max_seq_length at measurement time",
    },
    "metric_bundle.metrics": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "list of metric entries",
    },
    "metric_bundle.metrics[*].name": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "string, metric identifier",
    },
    "metric_bundle.metrics[*].value": {
        "type": "snapshot_evidence",
        "allowed_usage": "read_only",
        "can_affect_runtime": false,
        "constraint": "float, never compared against threshold at runtime",
    },
    "metric_bundle.metrics[*].phase": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "string, 'train' | 'val' | 'test'",
    },
    "metric_bundle.metrics[*].decode_dependent": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "bool, true for AR metrics, false for TF metrics",
    },
    "metric_bundle.epoch_context": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "dict with epoch, tf_ratio, ar_ratio at save time",
    },
    "metric_bundle.epoch_context.epoch": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "integer",
    },
    "metric_bundle.epoch_context.tf_ratio": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "float, 0.0 to 1.0",
    },
    "metric_bundle.epoch_context.ar_ratio": {
        "type": "snapshot_evidence",
        "allowed_usage": "write_once",
        "can_affect_runtime": false,
        "constraint": "float, 0.0 to 1.0",
    },

    # === LEGACY ===
    "val_loss": {
        "type": "legacy",
        "allowed_usage": "read_only",
        "can_affect_runtime": false,
        "constraint": "float | null, display only, also in metric_bundle.metrics",
    },
    "ar_token_acc": {
        "type": "legacy",
        "allowed_usage": "read_only",
        "can_affect_runtime": false,
        "constraint": "float | null, display only, also in metric_bundle.metrics",
    },
    "ar_seq_em": {
        "type": "legacy",
        "allowed_usage": "read_only",
        "can_affect_runtime": false,
        "constraint": "float | null, display only, also in metric_bundle.metrics",
    },
}

##############################################################################
# (E) LINT CHECKLIST — Codex executable rules
##############################################################################

# Each entry can be checked deterministically (true/false)
# Format: CHECK_ID | SCOPE | QUERY | EXPECTED_RESULT

LINT_RULES = [
    # Static import checks
    ["L001", "training/*.py",   "grep 'from gis_recommend.evidence'",            "NO_MATCH"],
    ["L002", "training/*.py",   "grep 'import gis_recommend.evidence'",          "NO_MATCH"],
    ["L003", "inference/*.py",  "grep 'from gis_recommend.evidence'",            "NO_MATCH"],
    ["L004", "inference/*.py",  "grep 'import gis_recommend.evidence'",          "NO_MATCH"],
    ["L005", "models/*.py",     "grep 'from gis_recommend.evidence'",            "NO_MATCH"],
    ["L006", "models/*.py",     "grep 'import gis_recommend.evidence'",          "NO_MATCH"],
    ["L007", "pipelines/*.py",  "grep 'from gis_recommend.evidence'",            "NO_MATCH"],
    ["L008", "pipelines/*.py",  "grep 'import gis_recommend.evidence'",          "NO_MATCH"],

    # Interpretive function names must not appear outside evidence/
    ["L009", "training/*.py",   "grep 'classify_checkpoint_validity'",           "NO_MATCH"],
    ["L010", "training/*.py",   "grep 'reconstruct_lineage'",                    "NO_MATCH"],
    ["L011", "training/*.py",   "grep 'recompute_metrics'",                      "NO_MATCH"],
    ["L012", "training/*.py",   "grep 'compare_metrics'",                        "NO_MATCH"],
    ["L013", "training/*.py",   "grep 'diff_dispatch'",                          "NO_MATCH"],
    ["L014", "training/*.py",   "grep 'generate_archaeology_report'",            "NO_MATCH"],
    ["L015", "inference/*.py",  "grep 'classify_checkpoint_validity|reconstruct_lineage|recompute_metrics|compare_metrics|diff_dispatch|generate_archaeology_report'", "NO_MATCH"],

    # Evidence module must not mutate state
    ["L016", "evidence/*.py",   "grep 'torch.save'",                             "NO_MATCH"],
    ["L017", "evidence/*.py",   "grep 'model.train()'",                          "NO_MATCH"],
    ["L018", "evidence/*.py",   "grep 'optimizer.step()'",                       "NO_MATCH"],
    ["L019", "evidence/*.py",   "grep 'loss.backward()'",                        "NO_MATCH"],
    ["L020", "evidence/*.py",   "grep 'model.load_state_dict'",                  "NO_MATCH"],
    ["L021", "evidence/*.py",   "grep 'DataLoader.*shuffle=True'",               "NO_MATCH"],

    # Runtime must not access snapshot fields for control flow
    ["L022", "training/*.py",   "grep 'checkpoint\\[.provenance.\\]' outside build_provenance_block", "NO_MATCH"],
    ["L023", "training/*.py",   "grep 'checkpoint\\[.metric_bundle.\\]' outside build_metric_bundle", "NO_MATCH"],
    ["L024", "training/*.py",   "grep 'if.*provenance.*:' with control flow impact", "NO_MATCH"],
    ["L025", "training/*.py",   "grep 'if.*metric_bundle.*:' with control flow impact", "NO_MATCH"],

    # Snapshot immutability: no load-modify-save patterns
    ["L026", "**/*.py",         "ast_detect: torch.load -> modify -> torch.save (same path)", "NO_MATCH"],

    # Gate enforcement: only 2 gates exist
    ["L027", "**/*.py",         "grep 'StructuralIncompatibilityError'",           "ONLY_IN: evidence._provenance.load_checkpoint"],
    ["L028", "**/*.py",         "grep 'if.*val_loss.*<' with sys.exit/raise",     "NO_MATCH"],
    ["L029", "**/*.py",         "grep 'if.*ar_token_acc.*<' with sys.exit/raise", "NO_MATCH"],

    # Provenance write-once: run_id consistency
    ["L030", "training/*.py",   "ast_check: self._provenance_block assigned exactly once per run", "PASS"],

    # decode_policy required when AR metrics present
    ["L031", "training/*.py",   "ast_check: build_metric_bundle() validates decode_policy non-null when decode_dependent metrics exist", "PASS"],

    # selector_policy always required
    ["L032", "training/*.py",   "ast_check: build_metric_bundle() validates selector_policy non-null", "PASS"],
]

##############################################################################
# (F) DETERMINISTIC VIOLATION DETECTION SIGNATURES
##############################################################################

# Each signature maps a code pattern to a violation type.
# Codex checks: IF signature matches THEN violation FLAG.

VIOLATION_SIGNATURES = {
    "VS001": {
        "pattern": "from gis_recommend.evidence import",
        "in_file_pattern": "training/*.py|inference/*.py|models/*.py|pipelines/*.py",
        "violation": "BoundaryViolation",
        "rule_ref": "no_evidence_import_in_training",
    },
    "VS002": {
        "pattern": "if.*provenance.*:.*raise|sys.exit|return None",
        "in_file_pattern": "training/*.py",
        "violation": "InterpretiveGateViolation",
        "rule_ref": "no_interpretive_output_controls_runtime",
    },
    "VS003": {
        "pattern": "if.*metric_bundle.*:.*raise|sys.exit|return None",
        "in_file_pattern": "training/*.py",
        "violation": "InterpretiveGateViolation",
        "rule_ref": "no_interpretive_output_controls_runtime",
    },
    "VS004": {
        "pattern": "torch.load(X); ... modify dict ...; torch.save(dict, X)",
        "in_file_pattern": "**/*.py",
        "violation": "SnapshotModificationViolation",
        "rule_ref": "snapshot_never_modified_after_save",
    },
    "VS005": {
        "pattern": "self._provenance_block = ...",
        "count_in_scope": "training.*.train",
        "expected_count": 1,
        "violation": "ProvenanceIntegrityError",
        "rule_ref": "provenance_write_once",
    },
    "VS006": {
        "pattern": "checkpoint_dict.provenance.run_id != ...",
        "in_file_pattern": "training/*.py",
        "context": "within same run",
        "violation": "ProvenanceIntegrityError",
        "rule_ref": "run_id_unchanged_within_run",
    },
    "VS007": {
        "pattern": "metric_bundle WITHOUT selector_policy",
        "in_function": "build_metric_bundle",
        "violation": "IncompleteMetricError",
        "rule_ref": "selector_policy_must_exist",
    },
    "VS008": {
        "pattern": "metric_bundle WITHOUT decode_policy WHEN any metric.decode_dependent==true",
        "in_function": "build_metric_bundle",
        "violation": "IncompleteMetricError",
        "rule_ref": "decode_policy_must_exist_when_decode_dependent_metrics_present",
    },
    "VS009": {
        "pattern": "raise StructuralIncompatibilityError",
        "allowed_locations": ["evidence._provenance.load_checkpoint"],
        "elsewhere": "InterpretiveGateViolation",
        "rule_ref": "format_version_gate + model_state_dict_shape_gate",
    },
    "VS010": {
        "pattern": "torch.save in evidence/",
        "in_file_pattern": "evidence/*.py",
        "violation": "BoundaryViolation",
        "rule_ref": "evidence_module_only_reads_snapshot",
    },
    "VS011": {
        "pattern": "model.train()|optimizer.step()|loss.backward() in evidence/",
        "in_file_pattern": "evidence/*.py",
        "violation": "BoundaryViolation",
        "rule_ref": "evidence_module_only_reads_snapshot",
    },
    "VS012": {
        "pattern": "provenance['parent_run_id'] = |provenance['run_id'] = ",
        "in_file_pattern": "**/*.py",
        "context": "after training completion",
        "violation": "ProvenanceViolation",
        "rule_ref": "provenance_no_backfill",
    },
}

##############################################################################
# END mvcs_v1.spec
##############################################################################
