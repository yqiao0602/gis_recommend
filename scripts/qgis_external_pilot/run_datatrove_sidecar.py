#!/usr/bin/env python3
"""Run pinned DataTrove exact/MinHash pipelines and emit report-only evidence."""

import argparse
import importlib.metadata
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_datatrove_sidecar import (
    MinHashSidecarConfig,
    normalize_datatrove_report,
    write_normalized_report,
)


class _DocumentCollector:
    def __init__(self) -> None:
        self.documents: list[Any] = []

    def __enter__(self) -> "_DocumentCollector":  # noqa: PYI034
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def write(self, document: Any, rank: int = 0) -> None:
        del rank
        self.documents.append(document)


def _read_documents(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows.sort(key=lambda row: row["record_id"])
    if len({row["record_id"] for row in rows}) != len(rows):
        raise ValueError("input record_id values must be unique")
    return rows


def _authority_clusters(rows: list[dict[str, Any]]) -> list[list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[row["normalized_source_body_sha256"]].append(row["record_id"])
    return sorted(
        (sorted(record_ids) for record_ids in grouped.values() if len(record_ids) > 1),
        key=lambda cluster: tuple(cluster),
    )


def run_datatrove(
    *,
    input_path: Path,
    work_dir: Path,
    output_path: Path,
    config: MinHashSidecarConfig,
) -> dict[str, Any]:
    """Run DataTrove locally in one process and normalize its evidence."""
    from datatrove.data import Document
    from datatrove.pipeline.dedup.exact_dedup import (
        ExactDedupConfig,
        ExactDedupFilter,
        ExactDedupSignature,
        ExactFindDedups,
    )
    from datatrove.pipeline.dedup.minhash import (
        MinhashConfig,
        MinhashDedupBuckets,
        MinhashDedupCluster,
        MinhashDedupFilter,
        MinhashDedupSignature,
    )
    from datatrove.utils.hashing import HashConfig
    from datatrove.utils.word_tokenizers import WordTokenizer

    class QgisSourceCodeTokenizer(WordTokenizer):
        def word_tokenize(self, text: str) -> list[str]:
            return re.findall(r"[^\W\d]\w*|\d+(?:\.\d+)?|[^\s]", text)

        def sent_tokenize(self, text: str) -> list[str]:
            return [text] if text else []

        def span_tokenize(self, text: str) -> list[tuple[int, int]]:
            return [(0, len(text))] if text else []

    rows = _read_documents(input_path)
    if work_dir.exists() and any(work_dir.iterdir()):
        raise ValueError(f"work directory must be empty: {work_dir}")
    work_dir.mkdir(parents=True, exist_ok=True)

    def make_documents() -> list[Any]:
        return [
            Document(
                id=row["record_id"],
                text=row["text"],
                metadata={
                    "normalized_source_body_sha256": row[
                        "normalized_source_body_sha256"
                    ]
                },
            )
            for row in rows
        ]

    def content_getter(document: Document) -> str:
        return document.text

    hash_config = HashConfig(
        precision=config.precision,
        hash_fc=config.hash_function,
    )
    exact_config = ExactDedupConfig(
        content_getter=content_getter,
        hash_config=hash_config,
        only_dedup_in_index=False,
    )
    exact_signatures = work_dir / "exact_signatures"
    exact_duplicates = work_dir / "exact_duplicates"
    ExactDedupSignature(str(exact_signatures), exact_config).run(
        iter(make_documents()), rank=0, world_size=1
    )
    ExactFindDedups(
        str(exact_signatures), str(exact_duplicates), exact_config
    ).run(None, rank=0, world_size=1)
    exact_excluded = _DocumentCollector()
    list(
        ExactDedupFilter(
            str(exact_duplicates),
            exact_config,
            exclusion_writer=exact_excluded,
        ).run(iter(make_documents()), rank=0, world_size=1)
    )

    expected_exact_clusters = _authority_clusters(rows)
    expected_excluded = {
        record_id
        for cluster in expected_exact_clusters
        for record_id in cluster[1:]
    }
    actual_excluded = {document.id for document in exact_excluded.documents}
    if actual_excluded != expected_excluded:
        raise ValueError(
            "DataTrove exact exclusions do not equal normalized-body authority: "
            f"expected={sorted(expected_excluded)} actual={sorted(actual_excluded)}"
        )

    minhash_config = MinhashConfig(
        n_grams=config.ngram_size,
        num_buckets=config.num_buckets,
        hashes_per_bucket=config.hashes_per_bucket,
        seed=config.seed,
        hash_config=hash_config,
    )
    minhash_signatures = work_dir / "minhash_signatures"
    minhash_buckets = work_dir / "minhash_buckets"
    minhash_clusters = work_dir / "minhash_clusters"
    MinhashDedupSignature(
        str(minhash_signatures),
        config=minhash_config,
        language=QgisSourceCodeTokenizer(),
    ).run(iter(make_documents()), rank=0, world_size=1)
    bucket_step = MinhashDedupBuckets(
        str(minhash_signatures),
        str(minhash_buckets),
        config=minhash_config,
        only_dedup_in_index=False,
    )
    for rank in range(config.num_buckets):
        bucket_step.run(None, rank=rank, world_size=config.num_buckets)
    MinhashDedupCluster(
        str(minhash_buckets),
        str(minhash_clusters),
        config=minhash_config,
        save_cluster_id=True,
        save_cluster_size=True,
    ).run(None, 0, world_size=1)

    minhash_excluded = _DocumentCollector()
    minhash_kept = list(
        MinhashDedupFilter(
            str(minhash_clusters),
            exclusion_writer=minhash_excluded,
            load_cluster_ids=True,
            load_cluster_sizes=True,
        ).run(iter(make_documents()), rank=0, world_size=1)
    )
    grouped_minhash: dict[int, list[str]] = defaultdict(list)
    for document in minhash_kept + minhash_excluded.documents:
        cluster_id = int(document.metadata.get("minhash_cluster_id", -1))
        if cluster_id >= 0:
            grouped_minhash[cluster_id].append(document.id)

    report = normalize_datatrove_report(
        rows,
        datatrove_version=importlib.metadata.version("datatrove"),
        datatrove_exact_clusters=expected_exact_clusters,
        datatrove_minhash_clusters=list(grouped_minhash.values()),
        config=config,
    )
    write_normalized_report(output_path, report)
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_datatrove(
        input_path=args.input,
        work_dir=args.work_dir,
        output_path=args.output,
        config=MinHashSidecarConfig(tokenizer="qgis_source_code_regex_v1"),
    )


if __name__ == "__main__":
    main()
