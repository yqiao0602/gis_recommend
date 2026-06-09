# GIS Recommend — Operator Recommendation System

Task-conditioned transformer model for recommending GIS operator sequences from natural language task descriptions.

**Current best model:** V4.2 (Top-1 accuracy: 56.2%)

---

## Installation

### Option 1: Minimal install (evaluation-only, CPU/GPU inference)

```bash
pip install -e .
```

This installs `numpy`, `torch`, `transformers`, `tqdm`, `pydantic` — enough to run
`gis-evaluate` without `--reranker-v3`, `--use-repair`, and without training.

### Option 2: With v3 reranker (semantic query matching)

```bash
pip install -e .[reranker-v3]
```

Adds `sentence-transformers` so that `gis-evaluate --reranker-v3` can load
`all-MiniLM-L6-v2` and compute `query_chain_sim`. Without this extra the v3
reranker silently degrades (see `--strict-encoder` to fail-fast instead).

### Option 3: Full stack (kg + repair + training + visualization)

```bash
pip install -e .[all]
```

Adds `neo4j`, `dgl`, `torchdata`, `matplotlib`, `seaborn`, `networkx`.

### Option 4: Exact reproducible lock

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

`requirements.txt` pins the exact versions validated on the training server
(torch 2.1.2, dgl 2.2.1, etc.).

---

## Running

**All commands must be run from the repo root** (the directory containing
`outputs/`), because `gis-evaluate` resolves `l3_embeddings.pt`,
`classification_hierarchy.csv`, and `dataset_splits_v4.json` relative to the
repo root.

### Evaluation CLI

```bash
# After pip install -e .
gis-evaluate --eval-mode dev --use-reranker --reranker-v3 --oracle \
    --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth \
    --sp-checkpoint outputs/set_predictor_checkpoints_v3/best_model.pth \
    --report-tag my-run

# Equivalent python -m invocation (no install required):
python -m gis_recommend.evaluation --eval-mode dev --use-reranker --reranker-v3 \
    --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth \
    --sp-checkpoint outputs/set_predictor_checkpoints_v3/best_model.pth \
    --report-tag my-run
```

**Flags worth knowing:**
- `--eval-mode {smoke|dev|full}` — `smoke=200 samples, dev=1000, full=all test split`
- `--use-reranker` — enable structured reranker (v2 StructuredReranker)
- `--reranker-v3` — switch to two-stage semantic reranker (requires `pip install -e .[reranker-v3]`)
- `--strict-encoder` — fail hard if v3 reranker can't load sentence-transformers (otherwise silently degrades)
- `--use-repair` — chain repair via Neo4j (requires `pip install -e .[kg]` + running Neo4j)
- `--oracle` — compute oracle upper bounds from top-N L3 candidates
- `--report-tag <name>` — archives the report under `outputs/evaluation_reports/evaluation-report-<name>-<ts>.json`

### Training

```bash
# After the 8-step data pipeline has run (outputs/pipeline/step8/ exists)
python -m gis_recommend.training.train_v4_2    # current best
python -m gis_recommend.training.train_v4_6    # latest, generally not better
```

### Interactive system (CLI REPL)

```bash
python -m gis_recommend.pipelines.interactive_system
```

### Data pipeline (one-time preprocessing)

```bash
python -m gis_recommend.data.pipeline_runner
```

---

## Package Structure

```
system_redesign/
├── pyproject.toml                    # Install spec + CLI entry points
├── requirements.txt                   # Reproducible exact-version lock
├── src/gis_recommend/
│   ├── config/                       # transformer_config.py is the single source of truth
│   ├── data/                         # 8-step workflow extraction & cleaning
│   ├── models/                       # Transformer V3/V4 + SetPredictor
│   ├── training/                     # train_v3.py, train_v4_2.py ... train_v4_6.py
│   ├── inference/                    # L3 beam search (V3 / V4 inferencer)
│   ├── operators/                    # L3→QGIS candidate generation, QA
│   ├── knowledge_graph/              # Neo4j GraphRAG, chain validator, chain repair
│   ├── reranking/                    # StructuredReranker (v2) + TwoStageReranker (v3)
│   ├── llm/                          # LLM pipeline: normalize, extract, template, scorer
│   ├── evaluation/                   # sampling / reranker_pipeline / diagnostics / report / runner
│   └── pipelines/                    # interactive_system + legacy demos
├── outputs/                           # Checkpoints, labeled data, reports
│   └── README.md                      # Authoritative data-path registry
├── scripts/                           # KG build, one-off analysis tools (NOT the evaluator)
├── tests/                             # unittest discovery root
├── archive/                           # Deprecated code retained for reference
└── docs/                              # Design specs, patent drafts
```

---

## Quick Python API

```python
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.config.transformer_config import OUTPUT_DIR, DEVICE

# Run the evaluation programmatically
from gis_recommend.evaluation import runner
runner.main()  # reads sys.argv; call via python -m for CLI args
```

---

## Migration Notes (2026-04)

- `scripts/evaluate_system.py` has been **removed**. Use `gis-evaluate` or
  `python -m gis_recommend.evaluation` instead.
- The 1595-line evaluation monolith is now split across
  `evaluation/{sampling, reranker_pipeline, diagnostics, report, runner}.py`.
- Two config files (`config/config.py` + `transformer_config.py`) are now one
  `config/transformer_config.py` with HGT-specific constants prefixed `HGT_`.
- Import-time side effects (`mkdir`, module-level `print`) are gone. Training
  scripts now call `ensure_output_dirs()` explicitly in `main()`.

---

## Known Limitations

- **CLI expects repo-root working directory.** `gis-evaluate` will not find
  `outputs/` / `classification_hierarchy.csv` if run from an unrelated directory.
  Always `cd` into the repo first.
- The `all-MiniLM-L6-v2` model auto-downloads on first run of `--reranker-v3`.
  For air-gapped deployment either pre-cache it or skip the flag.
- Neo4j (for `--use-repair` and the full pipeline) must be running at
  `bolt://localhost:7687` with auth `neo4j / 12345678` (see
  `interactive_system.py` defaults). Adjust via constructor args if different.
