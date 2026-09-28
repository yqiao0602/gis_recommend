#!/usr/bin/env python3
"""Build the `paper_v1_128` vocab profile for the M1 V4.6 controlled rerun.

paper_v1's L3 vocabulary is the frozen 128-token taxonomy (tokens 0-127), while
every existing V4 profile is 94/107/124. Running M1-R1 under a mismatched
profile would either fail closed (as the smoke did) or silently drop classes,
so the controlled rerun gets its own isolated profile — exactly the pattern the
stable124 experiment profile established (94 rows reused verbatim, extensions
seeded deterministically).

Outputs (all under docs/reports/paper_v1_profile_v1/):
  id_mappings_paper_v1_128.json    128 code -> token mapping from the authority
  l3_embeddings_paper_v1_128.pt    128x256 (rows 0-93 reused, 94-127 seeded)
  task_type_vocabulary_paper_v1.json
  task_type_length_stats_paper_v1.json
  transition_allowed_next_paper_v1.json
  manifest_paper_v1_profile_v1.json  hashes of every input and output

The production `v2_94_stable` profile and the stable124 experiment are not
touched; the profile is selected only via GIS_VOCAB_PROFILE=paper_v1_128.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMBEDDINGS = ROOT / "outputs_v2/l3_embeddings_v2.pt"
EMBEDDING_SEED = 128256


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=ROOT / "docs/reports/paper_v1_supervision/paper_v1_supervision_manifest.jsonl")
    ap.add_argument("--taxonomy", type=Path, default=ROOT / "docs/reports/qgis_taxonomy_128_authority_v1/taxonomy_128_v1.json")
    ap.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS)
    ap.add_argument("--output", type=Path, default=ROOT / "docs/reports/paper_v1_profile_v1")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    classes = sorted(taxonomy["classes"], key=lambda c: c["token_id"])
    if len(classes) != 128 or [c["token_id"] for c in classes] != list(range(128)):
        raise ValueError("taxonomy is not 128 contiguous tokens")

    # ── id mappings: code -> token id (the V4 trainer reads primary_l3 style) ──
    mapping = {
        "schema": "gis_recommend.paper_v1_id_mappings.v1",
        "vocab_size": 128,
        "mapping_metadata": {
            "qgis_to_l3": {
                c["l3_code"]: {"primary_l3": c["l3_code"], "token_id": c["token_id"],
                               "l3_name": c["l3_name"]}
                for c in classes
            },
            "source": "taxonomy_128_v1 (frozen authority)",
        },
    }
    (args.output / "id_mappings_paper_v1_128.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── embeddings: 94 reused verbatim, 128-94=34 appended deterministically ──
    base = torch.load(args.embeddings, map_location="cpu", weights_only=True)
    if isinstance(base, dict):
        base = base.get("embeddings", base.get("weight"))
    if tuple(base.shape) != (94, 256):
        raise ValueError(f"expected base embeddings [94,256], got {tuple(base.shape)}")
    generator = torch.Generator(device="cpu").manual_seed(EMBEDDING_SEED)
    extended = torch.cat([base, torch.randn((128 - 94, 256), generator=generator, dtype=base.dtype)])
    torch.save(extended, args.output / "l3_embeddings_paper_v1_128.pt")

    # ── task vocabulary / length stats / transition table from paper_v1 train ──
    rows = read_jsonl(args.manifest)
    train = [r for r in rows if r["split"] == "train" and r["task_text"].strip() and r["l3_chain"]]
    val = [r for r in rows if r["split"] == "val" and r["task_text"].strip() and r["l3_chain"]]
    if len(train) != 8817 or len(val) != 49:
        raise ValueError(f"unexpected split sizes train={len(train)} val={len(val)}")

    task_types = sorted({r["task_type"] or "Unknown" for r in train} - {"Unknown"})
    vocab = {"task_type_to_id": {"Unknown": 0}, "id_to_task_type": {"0": "Unknown"},
             "num_types": 1}
    for index, name in enumerate(task_types, start=1):
        vocab["task_type_to_id"][name] = index
        vocab["id_to_task_type"][str(index)] = name
        vocab["num_types"] += 1
    (args.output / "task_type_vocabulary_paper_v1.json").write_text(
        json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")

    code_to_token = {c["l3_code"]: c["token_id"] for c in classes}
    lengths: defaultdict[str, list[int]] = defaultdict(list)
    transitions: defaultdict[int, Counter] = defaultdict(Counter)
    for r in train:
        task = r["task_type"] or "Unknown"
        tokens = [code_to_token[c] for c in r["l3_chain"]]
        lengths[task].append(len(tokens))
        for a, b in zip(tokens, tokens[1:]):
            transitions[a][b] += 1
    stats = {task: {"count": len(v), "mean": sum(v) / len(v), "min": min(v), "max": max(v)}
             for task, v in lengths.items()}
    (args.output / "task_type_length_stats_paper_v1.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "transition_allowed_next_paper_v1.json").write_text(
        json.dumps({str(k): dict(v) for k, v in transitions.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    manifest = {
        "schema": "gis_recommend.paper_v1_profile.v1",
        "profile": "paper_v1_128",
        "content_vocab_size": 128,
        "model_vocab_size": 132,
        "embedding_seed": EMBEDDING_SEED,
        "embedding_shape": list(extended.shape),
        "train_rows": len(train),
        "val_rows": len(val),
        "task_types": vocab["num_types"],
        "outputs": {p.name: sha256_file(p) for p in sorted(args.output.glob("*")) if p.name != "manifest_paper_v1_profile_v1.json"},
        "inputs": {
            str(args.manifest): sha256_file(args.manifest),
            str(args.taxonomy): sha256_file(args.taxonomy),
            str(args.embeddings): sha256_file(args.embeddings),
        },
        "note": "isolated M1-R1 profile; production v2_94_stable and stable124 untouched",
    }
    (args.output / "manifest_paper_v1_profile_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("profile", "content_vocab_size", "model_vocab_size",
                                               "train_rows", "val_rows", "task_types")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
