#!/usr/bin/env bash
# =============================================================================
# server_bootstrap.sh — one-shot, IDEMPOTENT bootstrap of this project onto the
# compute server (qy@10.191.2.38). Run it from the LOCAL repo root (Git Bash).
#
# What it does:
#   1. preflight  : check ssh/rsync, test connectivity
#   2. code sync  : rsync repo source (src/scripts/tests/configs), skipping junk
#   3. data sync  : rsync the MINIMAL data manifest needed to run V4.6 eval/train
#                   (rsync skips already-synced/unchanged files — safe to re-run)
#   4. remote env : create/reuse a py3.10 venv, pip install -e .
#   5. verify     : torch + CUDA + key imports + dataset presence
#
# Layout note (IMPORTANT): qgis_operator_registry.py resolves the operators file
# as parents[4]/operators-json/qgis_operators.json, i.e. operators-json sits in
# the PARENT of the repo dir. So the remote layout mirrors local:
#     $REMOTE_ROOT/system_redesign   (this repo)
#     $REMOTE_ROOT/operators-json    (sibling)
#
# Auth (no password is hard-coded):
#   Preferred — set up a key once, then this script is passwordless:
#       ssh-copy-id qy@10.191.2.38
#   Or — export the password for this run (uses sshpass if available):
#       export SSHPASS='...'; ./scripts/server_bootstrap.sh
#
# Common overrides (env vars):
#   SERVER=qy@10.191.2.38  REMOTE_ROOT=~/Algorithm_classification
#   PUSH_CKPT=1   also sync the (large) V4.6 + set-predictor checkpoints
#   PUSH_HF=1     also sync local HuggingFace bert-base-uncased cache
#   DRY_RUN=1     rsync --dry-run everywhere (preview only, transfers nothing)
# =============================================================================
set -euo pipefail

# ── config ───────────────────────────────────────────────────────────────────
SERVER="${SERVER:-qy@10.191.2.38}"
REMOTE_ROOT="${REMOTE_ROOT:-\$HOME/Algorithm_classification}"   # expanded remotely
REMOTE_REPO="$REMOTE_ROOT/system_redesign"
REMOTE_OPS="$REMOTE_ROOT/operators-json"
PY="${PY:-python3.10}"
PUSH_CKPT="${PUSH_CKPT:-0}"
PUSH_HF="${PUSH_HF:-0}"
DRY_RUN="${DRY_RUN:-0}"

LOCAL_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_ROOT="$(cd "$LOCAL_REPO/.." && pwd)"          # parent holding operators-json

# ssh / rsync transport (uses sshpass only if SSHPASS is set AND key auth absent)
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15"
if [ -n "${SSHPASS:-}" ] && command -v sshpass >/dev/null 2>&1; then
  SSH="sshpass -e ssh $SSH_OPTS"
  RSYNC_RSH="sshpass -e ssh $SSH_OPTS"
else
  SSH="ssh $SSH_OPTS"
  RSYNC_RSH="ssh $SSH_OPTS"
fi
RSYNC_FLAGS="-az --human-readable --info=stats1,progress2"
[ "$DRY_RUN" = "1" ] && RSYNC_FLAGS="$RSYNC_FLAGS --dry-run"

say() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
run_remote() { $SSH "$SERVER" "bash -lc '$*'"; }

# ── 1. preflight ───────────────────────────────────────────────────────────────
say "1/5 preflight"
command -v rsync >/dev/null 2>&1 || { echo "ERROR: rsync not found (install rsync or use scp fallback)"; exit 1; }
echo "local repo : $LOCAL_REPO"
echo "local root : $LOCAL_ROOT  (operators-json must be here)"
echo "server     : $SERVER"
echo "remote repo: $REMOTE_REPO"
$SSH "$SERVER" 'echo "  connected: $(hostname) | $(uname -s) | $('"$PY"' --version 2>&1 || echo no-'"$PY"')"' \
  || { echo "ERROR: cannot ssh to $SERVER (set up key or export SSHPASS)"; exit 1; }
run_remote "mkdir -p '$REMOTE_REPO' '$REMOTE_OPS'"

# ── 2. code sync ────────────────────────────────────────────────────────────────
say "2/5 code sync (src/scripts/tests/configs)"
rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
  --exclude '.git/' --exclude '__pycache__/' --exclude '*.pyc' \
  --exclude 'outputs/' --exclude 'outputs_v2/' --exclude 'archive/' \
  --exclude '爬取GithubQGIS/' --exclude 'docs/相关文献/' \
  --exclude '.codegraph/' --exclude '.omx/' --exclude '.claude/' --exclude '.tmp_test/' \
  --include 'src/***' --include 'scripts/***' --include 'tests/***' \
  --include 'pyproject.toml' --include 'requirements.txt' \
  --include '*.md' --include 'docs/' --include 'docs/**' \
  --exclude '*' \
  "$LOCAL_REPO/" "$SERVER:$REMOTE_REPO/"

# ── 3. data sync (minimal manifest; rsync skips unchanged) ──────────────────────
say "3/5 data sync (minimal manifest)"
STEP8="outputs_v2/pipeline/step8_quality_gate"
# 3a. step8 training/eval artifacts (labeled_workflows, splits, vocab, length stats)
run_remote "mkdir -p '$REMOTE_REPO/$STEP8'"
rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
  "$LOCAL_REPO/$STEP8/" "$SERVER:$REMOTE_REPO/$STEP8/"
# 3b. outputs_v2 contract + landing files (flat)
for f in \
  id_mappings_v2.json classification_hierarchy_v2.csv l3_vocab_v2.json \
  transition_allowed_next.json dataset_splits_v4.json \
  qgis_chain_dataset.jsonl qgis_chain_dataset_v2_enriched_v3.jsonl \
  qgis_operator_io_types.json ; do
  if [ -f "$LOCAL_REPO/outputs_v2/$f" ]; then
    rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
      "$LOCAL_REPO/outputs_v2/$f" "$SERVER:$REMOTE_REPO/outputs_v2/$f"
  else
    echo "  [skip] missing locally: outputs_v2/$f"
  fi
done
# 3c. operators-json (PARENT-level sibling — keeps parents[4] resolution intact)
rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
  "$LOCAL_ROOT/operators-json/qgis_operators.json" "$SERVER:$REMOTE_OPS/qgis_operators.json"
# 3d. QGIS catalog (inside repo root, used by the showcase landing planner)
if [ -f "$LOCAL_REPO/爬取GithubQGIS/QGIS_Input.csv" ]; then
  run_remote "mkdir -p '$REMOTE_REPO/爬取GithubQGIS'"
  rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
    "$LOCAL_REPO/爬取GithubQGIS/QGIS_Input.csv" "$SERVER:$REMOTE_REPO/爬取GithubQGIS/QGIS_Input.csv"
fi
# 3e. checkpoints (LARGE — opt-in via PUSH_CKPT=1)
if [ "$PUSH_CKPT" = "1" ]; then
  for d in \
    transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed \
    set_predictor_checkpoints_v3_quality_gate_v4_6 \
    transformer_checkpoints_v4_6_quality_gate ; do
    if [ -d "$LOCAL_REPO/outputs_v2/$d" ]; then
      run_remote "mkdir -p '$REMOTE_REPO/outputs_v2/$d'"
      rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
        "$LOCAL_REPO/outputs_v2/$d/" "$SERVER:$REMOTE_REPO/outputs_v2/$d/"
    fi
  done
else
  echo "  [info] checkpoints NOT pushed (set PUSH_CKPT=1 to include the V4.6 .pth files)"
fi
# 3f. HuggingFace bert-base-uncased cache (opt-in; else allow download on server)
if [ "$PUSH_HF" = "1" ] && [ -d "$HOME/.cache/huggingface" ]; then
  rsync $RSYNC_FLAGS -e "$RSYNC_RSH" \
    --include '*bert-base-uncased*/***' --include '*/' --exclude '*' \
    "$HOME/.cache/huggingface/" "$SERVER:\$HOME/.cache/huggingface/" || true
fi

# ── 4. remote env (venv + deps; reuse if present) ───────────────────────────────
say "4/5 remote env (venv + pip install -e .)"
run_remote "cd '$REMOTE_REPO' && \
  ( [ -d .venv ] || $PY -m venv .venv ) && \
  . .venv/bin/activate && \
  python -m pip install -U pip wheel >/dev/null && \
  ( pip install -e . || pip install -r requirements.txt )"

# ── 5. verify ───────────────────────────────────────────────────────────────────
say "5/5 verify"
run_remote "cd '$REMOTE_REPO' && . .venv/bin/activate && \
  python - <<'PY'
import torch, importlib
print('torch', torch.__version__, '| cuda', torch.cuda.is_available(),
      '|', (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'))
for m in ('transformers','gis_recommend.evaluation.qgis_chain_metrics',
          'gis_recommend.inference.infer_l3_candidates_v4'):
    try: importlib.import_module(m); print('import OK:', m)
    except Exception as e: print('import FAIL:', m, '->', repr(e))
import os
for p in ('$STEP8/labeled_workflows_l3_v4_quality_gate.json',
          'outputs_v2/qgis_chain_dataset.jsonl',
          '../operators-json/qgis_operators.json'):
    print(('present' if os.path.exists(p) else 'MISSING'), p)
PY"

say "done — to run on the server"
cat <<EOF
  ssh $SERVER
  cd $REMOTE_REPO && . .venv/bin/activate
  # Phase A (open-landing, text-only):
  python scripts/build_open_landing_taskfile.py
  python scripts/run_end_to_end_showcase_eval.py \\
    --task-file outputs_v2/diagnostics/open_landing_v46/open_landing_tasks.jsonl \\
    --output-dir outputs_v2/diagnostics/open_landing_v46/        # add --allow-bert-download if no HF cache
  python scripts/score_v46_open_landing.py
  # Phase B (held-out, ③ correctness):
  python scripts/build_heldout_taskfile.py --max-samples 150
  python scripts/run_end_to_end_showcase_eval.py \\
    --task-file outputs_v2/diagnostics/heldout_v46/heldout_tasks.jsonl \\
    --output-dir outputs_v2/diagnostics/heldout_v46/
  python scripts/score_heldout_v46.py
  # pull reports back:  rsync -az $SERVER:$REMOTE_REPO/outputs_v2/diagnostics/ ./outputs_v2/diagnostics/
EOF
