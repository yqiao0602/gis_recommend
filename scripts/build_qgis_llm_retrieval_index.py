#!/usr/bin/env python3
"""Build a frozen local retrieval index for the isolated QGIS LLM pilot.

The index has two document kinds: catalog operators and L3 registry entries.
It is a candidate-retrieval aid only.  Similarity is never a training label,
operator canonicalization decision, or L3 mapping decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA = "gis_recommend.qgis_llm_retrieval_index.v1"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def build_documents(catalog: dict[str, Any], taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for row in catalog.get("operators", []):
        operator_id = str(row.get("operator_id") or "").strip().lower()
        if not operator_id:
            continue
        inputs = " ".join(str(value) for value in row.get("input_types", []))
        outputs = " ".join(str(value) for value in row.get("output_types", []))
        documents.append(
            {
                "document_id": f"operator:{operator_id}",
                "kind": "operator",
                "operator_id": operator_id,
                "text": " ".join(
                    value
                    for value in (
                        operator_id,
                        str(row.get("official_name") or ""),
                        str(row.get("provider") or ""),
                        inputs,
                        outputs,
                    )
                    if value
                ),
            }
        )
    for row in taxonomy.get("classes", []):
        l3_code = str(row.get("l3_code") or "").strip()
        if not l3_code:
            continue
        documents.append(
            {
                "document_id": f"l3:{l3_code}",
                "kind": "l3",
                "l3_code": l3_code,
                "token_id": row.get("token_id"),
                "text": " ".join(
                    value
                    for value in (
                        l3_code,
                        str(row.get("l3_name") or ""),
                        str(row.get("l3_description") or ""),
                    )
                    if value
                ),
            }
        )
    return sorted(documents, key=lambda row: str(row["document_id"]))


def rank_documents(
    query_embeddings: np.ndarray,
    documents: list[dict[str, Any]],
    document_embeddings: np.ndarray,
    *,
    top_k: int,
    kind: str | None = None,
) -> list[list[dict[str, Any]]]:
    if len(documents) != len(document_embeddings):
        raise ValueError("document metadata and embedding count differ")
    allowed = np.array(
        [kind is None or row["kind"] == kind for row in documents], dtype=bool
    )
    if not allowed.any():
        raise ValueError(f"no documents of requested kind: {kind}")
    scores = query_embeddings @ document_embeddings.T
    results: list[list[dict[str, Any]]] = []
    for query_scores in scores:
        candidates = [
            {
                "document_id": documents[index]["document_id"],
                "kind": documents[index]["kind"],
                "score": round(float(query_scores[index]), 8),
                **({"operator_id": documents[index]["operator_id"]} if "operator_id" in documents[index] else {}),
                **({"l3_code": documents[index]["l3_code"]} if "l3_code" in documents[index] else {}),
            }
            for index in np.flatnonzero(allowed)
        ]
        results.append(
            sorted(candidates, key=lambda row: (-float(row["score"]), row["document_id"]))[:top_k]
        )
    return results


def _load_queries(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if not isinstance(row.get("query_text"), str):
                    raise ValueError("each query must provide string query_text")
                yield row


def _load_encoder(model_name: str) -> Any:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, local_files_only=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    if args.top_k < 1:
        raise ValueError("top-k must be positive")

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    documents = build_documents(catalog, taxonomy)
    if not documents:
        raise ValueError("catalog and taxonomy produced no index documents")
    encoder = _load_encoder(args.model)
    embeddings = encoder.encode(
        [row["text"] for row in documents],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).astype(np.float32)

    document_path = args.output_dir / "documents_v1.jsonl"
    embedding_path = args.output_dir / "embeddings_v1.npy"
    summary_path = args.output_dir / "summary_v1.json"
    _atomic_write(
        document_path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in documents),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.save(embedding_path, embeddings, allow_pickle=False)
    summary: dict[str, Any] = {
        "schema": f"{SCHEMA}.summary",
        "model": args.model,
        "embedding_dimension": int(embeddings.shape[1]),
        "document_count": len(documents),
        "operator_document_count": sum(row["kind"] == "operator" for row in documents),
        "l3_document_count": sum(row["kind"] == "l3" for row in documents),
        "training_admission": "not_granted_retrieval_index_only",
        "training_rows_emitted": 0,
    }
    if args.queries:
        queries = list(_load_queries(args.queries))
        query_embeddings = encoder.encode(
            [str(row["query_text"]) for row in queries],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        results = rank_documents(
            query_embeddings, documents, embeddings, top_k=args.top_k, kind="operator"
        )
        result_path = args.output_dir / "query_results_v1.jsonl"
        _atomic_write(
            result_path,
            "".join(
                json.dumps(
                    {
                        "query_id": query.get("query_id"),
                        "query_text_sha256": hashlib.sha256(str(query["query_text"]).encode("utf-8")).hexdigest(),
                        "operator_candidates": candidates,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
                for query, candidates in zip(queries, results)
            ),
        )
        summary["query_count"] = len(queries)

    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    artifacts = [document_path, embedding_path, summary_path]
    result_path = args.output_dir / "query_results_v1.jsonl"
    if result_path.is_file():
        artifacts.append(result_path)
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {args.catalog.name: _sha256(args.catalog), args.taxonomy.name: _sha256(args.taxonomy)},
                "artifacts": {path.name: _sha256(path) for path in artifacts},
                "model": args.model,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
