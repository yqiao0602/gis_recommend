from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _canonical_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_bytes(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ).encode("utf-8")
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_record(
    source_root: Path, relative_path: str, source: str
) -> dict[str, object]:
    source_path = source_root / relative_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source = source + " " * max(0, 220 - len(source.encode("utf-8")))
    source_path.write_text(source, encoding="utf-8")
    return {
        "record_key": relative_path,
        "source_path": relative_path,
        "source_sha256": _sha256(source_path),
        "instances": [{"source_path": relative_path}],
    }


def _authority_files(
    tmp_path: Path,
    records: list[dict[str, object]],
    *,
    exact_paths: list[str] | None = None,
) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "sources"
    source_root.mkdir(exist_ok=True)
    canonical = tmp_path / "canonical.jsonl"
    _canonical_jsonl(
        canonical,
        sorted(records, key=lambda row: str(row["source_sha256"])),
    )
    join = tmp_path / "join.jsonl"
    if exact_paths is None:
        exact_paths = [str(row["source_path"]) for row in records]
    _canonical_jsonl(
        join,
        [
            {
                "join_status": "authoritative_exact_batch_join",
                "source_path": source_path,
            }
            for source_path in exact_paths
        ],
    )
    return canonical, join, source_root


def _run(
    input_paths: list[Path],
    output_dir: Path,
    *,
    canonical: Path,
    join: Path,
    source_root: Path,
) -> dict[str, object]:
    from scripts.build_gee_source_exclusion_authority import main

    argv: list[str] = []
    for path in input_paths:
        argv.extend(("--input-manifest", str(path)))
    argv.extend(
        (
            "--canonical-manifest",
            str(canonical),
            "--join-ledger",
            str(join),
            "--source-root",
            str(source_root),
            "--output-dir",
            str(output_dir),
        )
    )
    return main(argv)


def _valid_fixture(
    tmp_path: Path,
) -> tuple[list[Path], Path, Path, Path, list[dict[str, object]]]:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    records = [
        _source_record(
            source_root,
            "data/a.js",
            "var x = ee.Image('A'); Export.image.toDrive({image: x});",
        ),
        _source_record(
            source_root,
            "data/b.js",
            "function clipIt(x) { return x.clip(roi); }\n"
            "var y = clipIt(ee.Image('B')); Export.image.toDrive({image: y});",
        ),
    ]
    canonical = tmp_path / "canonical.jsonl"
    _canonical_jsonl(
        canonical,
        sorted(records, key=lambda row: str(row["source_sha256"])),
    )
    join = tmp_path / "join.jsonl"
    _canonical_jsonl(
        join,
        [
            {
                "join_status": "authoritative_exact_batch_join",
                "source_path": row["source_path"],
            }
            for row in records
        ],
    )
    first = tmp_path / "first-selection.jsonl"
    second = tmp_path / "second-audit.jsonl"
    _canonical_jsonl(
        first,
        [
            {
                "source_sha256": records[1]["source_sha256"],
                "source_path": records[1]["source_path"],
            },
            {
                "source_sha256": records[0]["source_sha256"],
                "record_key": records[0]["record_key"],
            },
        ],
    )
    _canonical_jsonl(
        second,
        [
            {
                "source_sha256": records[1]["source_sha256"],
                "source_path": records[1]["source_path"],
                "record_key": records[1]["record_key"],
            },
            {
                "source_sha256": records[0]["source_sha256"],
                "source_path": records[0]["source_path"],
            },
        ],
    )
    return [first, second], canonical, join, source_root, records


def test_builds_selector_consumable_exclusion_and_provenance_outputs(
    tmp_path: Path,
) -> None:
    inputs, canonical, join, source_root, records = _valid_fixture(tmp_path)

    result = _run(
        inputs,
        tmp_path / "output",
        canonical=canonical,
        join=join,
        source_root=source_root,
    )

    output_dir = tmp_path / "output"
    authority = _read_jsonl(output_dir / "source_exclusion_authority.jsonl")
    assert [row["source_sha256"] for row in authority] == sorted(
        str(row["source_sha256"]) for row in records
    )
    assert all(
        row["schema"] == "gis_recommend.gee_source_exclusion.v1" for row in authority
    )
    selection = _read_jsonl(output_dir / "exclusion_selection.jsonl")
    selection_fields = {
        "record_key",
        "source_path",
        "source_sha256",
        "size_bytes",
        "facts_supported",
        "calibration_stratum",
    }
    assert all(set(row) == selection_fields for row in selection)
    assert [row["source_sha256"] for row in selection] == sorted(
        str(row["source_sha256"]) for row in records
    )
    assert {row["calibration_stratum"] for row in selection} == {
        "linear_export",
        "helper_export",
    }
    assert all(row["facts_supported"] is True for row in selection)

    from scripts.build_gee_workflow_dag_calibration import (
        _load_fixed_selection_records,
    )

    loaded = _load_fixed_selection_records(
        output_dir / "exclusion_selection.jsonl", source_root
    )
    assert len(loaded) == 2

    provenance = _read_jsonl(output_dir / "exclusion_provenance.jsonl")
    assert [row["source_sha256"] for row in provenance] == [
        row["source_sha256"] for row in selection
    ]
    assert all(
        {item["kind"] for item in row["input_artifacts"]} == {"source_request_manifest"}
        for row in provenance
    )
    assert all(
        {item["kind"] for item in row["authority_artifacts"]}
        == {"canonical_manifest", "exact_join_ledger", "source_file"}
        for row in provenance
    )
    assert all(
        item["path"] in {path.resolve().as_posix() for path in inputs}
        for row in provenance
        for item in row["input_artifacts"]
    )

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "duplicate_row_count": 2,
        "input_manifest_count": 2,
        "input_row_count": 4,
        "non_selector_compatible_reasons": {},
        "non_selector_compatible_source_count": 0,
        "schema": "gis_recommend.gee_source_exclusion_summary.v1",
        "selector_compatible_source_count": 2,
        "training_admission": "not_granted_exclusion_only",
        "training_rows_emitted": 0,
        "unique_source_count": 2,
    }
    assert result["summary"] == summary

    ledger = json.loads((output_dir / "hash_ledger.json").read_text(encoding="utf-8"))
    assert ledger["authority_inputs"] == [
        {
            "kind": "canonical_manifest",
            "path": canonical.resolve().as_posix(),
            "sha256": _sha256(canonical),
            "size_bytes": canonical.stat().st_size,
        },
        {
            "kind": "exact_join_ledger",
            "path": join.resolve().as_posix(),
            "sha256": _sha256(join),
            "size_bytes": join.stat().st_size,
        },
        {"kind": "source_root", "path": source_root.resolve().as_posix()},
    ]
    assert set(ledger["artifacts"]) == {
        "exclusion_provenance.jsonl",
        "exclusion_selection.jsonl",
        "non_selector_compatible_sources.jsonl",
        "report.md",
        "source_exclusion_authority.jsonl",
        "summary.json",
    }
    for name, metadata in ledger["artifacts"].items():
        artifact = output_dir / name
        assert metadata == {
            "sha256": _sha256(artifact),
            "size_bytes": artifact.stat().st_size,
        }


def test_preserves_non_export_authority_outside_selector_input(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    eligible = _source_record(
        source_root,
        "data/eligible.js",
        "var x = ee.Image('A'); Export.image.toDrive({image: x});",
    )
    non_export = _source_record(
        source_root,
        "data/non_export.js",
        "var x = ee.Image('B'); print(x);",
    )
    records = [eligible, non_export]
    canonical, join, _ = _authority_files(tmp_path, records)
    manifest = tmp_path / "history.jsonl"
    _canonical_jsonl(
        manifest,
        [{"source_sha256": row["source_sha256"]} for row in records],
    )

    _run(
        [manifest],
        tmp_path / "output",
        canonical=canonical,
        join=join,
        source_root=source_root,
    )

    output_dir = tmp_path / "output"
    authority = _read_jsonl(output_dir / "source_exclusion_authority.jsonl")
    assert {row["source_sha256"] for row in authority} == {
        row["source_sha256"] for row in records
    }
    selection = _read_jsonl(output_dir / "exclusion_selection.jsonl")
    assert [row["source_sha256"] for row in selection] == [
        eligible["source_sha256"]
    ]
    incompatible = _read_jsonl(
        output_dir / "non_selector_compatible_sources.jsonl"
    )
    assert incompatible == [
        {
            "schema": "gis_recommend.gee_source_exclusion_incompatible.v1",
            "source_path": non_export["source_path"],
            "source_sha256": non_export["source_sha256"],
            "selector_compatible": False,
            "reasons": ["missing_export_sink"],
        }
    ]
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["unique_source_count"] == 2
    assert summary["selector_compatible_source_count"] == 1
    assert summary["non_selector_compatible_source_count"] == 1
    assert summary["non_selector_compatible_reasons"] == {"missing_export_sink": 1}


def test_rejects_one_source_path_bound_to_different_source_hashes(
    tmp_path: Path,
) -> None:
    canonical, join, source_root = _authority_files(tmp_path, [])
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _canonical_jsonl(
        first,
        [{"source_sha256": "a" * 64, "source_path": "data/shared.js"}],
    )
    _canonical_jsonl(
        second,
        [{"source_sha256": "b" * 64, "record_key": "data/shared.js"}],
    )

    with pytest.raises(ValueError, match="different source SHA256"):
        _run(
            [first, second],
            tmp_path / "output",
            canonical=canonical,
            join=join,
            source_root=source_root,
        )


@pytest.mark.parametrize(
    "content, expected_message",
    [
        ("", "must not be empty"),
        ('{"source_sha256":"ABC"}\n', "invalid source_sha256"),
        ("[]\n", "JSON object"),
        ("{not-json}\n", "invalid JSON"),
    ],
)
def test_rejects_empty_or_invalid_manifest_rows(
    tmp_path: Path, content: str, expected_message: str
) -> None:
    canonical, join, source_root = _authority_files(tmp_path, [])
    manifest = tmp_path / "invalid.jsonl"
    manifest.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=expected_message):
        _run(
            [manifest],
            tmp_path / "output",
            canonical=canonical,
            join=join,
            source_root=source_root,
        )


@pytest.mark.parametrize("failure", ["missing", "duplicate", "no_exact_join"])
def test_every_requested_sha_must_uniquely_backjoin_with_exact_facts_support(
    tmp_path: Path, failure: str
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    record = _source_record(
        source_root,
        "data/source.js",
        "var x = ee.Image('A'); Export.image.toDrive({image: x});",
    )
    manifest = tmp_path / "requested.jsonl"
    _canonical_jsonl(manifest, [{"source_sha256": record["source_sha256"]}])
    canonical_records = [] if failure == "missing" else [record]
    if failure == "duplicate":
        canonical_records.append(dict(record))
    canonical = tmp_path / "canonical.jsonl"
    _canonical_jsonl(canonical, canonical_records)
    join = tmp_path / "join.jsonl"
    exact_paths = [] if failure == "no_exact_join" else [str(record["source_path"])]
    _canonical_jsonl(
        join,
        [
            {
                "join_status": "authoritative_exact_batch_join",
                "source_path": path,
            }
            for path in exact_paths
        ],
    )

    expected = (
        "exact facts support" if failure == "no_exact_join" else "uniquely backjoin"
    )
    with pytest.raises(ValueError, match=expected):
        _run(
            [manifest],
            tmp_path / "output",
            canonical=canonical,
            join=join,
            source_root=source_root,
        )


def test_malformed_canonical_source_sha_fails_closed(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    manifest = tmp_path / "requested.jsonl"
    _canonical_jsonl(manifest, [{"source_sha256": "a" * 64}])
    canonical = tmp_path / "canonical.jsonl"
    _canonical_jsonl(canonical, [{"source_sha256": []}])
    join = tmp_path / "join.jsonl"
    _canonical_jsonl(join, [])

    with pytest.raises(ValueError, match="canonical manifest.*invalid source_sha256"):
        _run(
            [manifest],
            tmp_path / "output",
            canonical=canonical,
            join=join,
            source_root=source_root,
        )


@pytest.mark.parametrize("failure", ["escape", "hash"])
def test_source_identity_failures_are_fail_closed(
    tmp_path: Path, failure: str
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    body = "var x = ee.Image('A'); Export.image.toDrive({image: x});"
    relative_path = "data/source.js"
    record = _source_record(source_root, relative_path, body)
    if failure == "escape":
        outside = tmp_path / "outside.js"
        outside.write_bytes((source_root / relative_path).read_bytes())
        record["source_path"] = "../outside.js"
        record["record_key"] = "../outside.js"
        record["instances"] = [{"source_path": "../outside.js"}]
        relative_path = "../outside.js"
    elif failure == "hash":
        source_path = source_root / relative_path
        original = source_path.read_bytes()
        source_path.write_bytes(b"X" + original[1:])
    manifest = tmp_path / "requested.jsonl"
    _canonical_jsonl(manifest, [{"source_sha256": record["source_sha256"]}])
    canonical = tmp_path / "canonical.jsonl"
    _canonical_jsonl(canonical, [record])
    join = tmp_path / "join.jsonl"
    _canonical_jsonl(
        join,
        [
            {
                "join_status": "authoritative_exact_batch_join",
                "source_path": relative_path,
            }
        ],
    )

    expected = {
        "escape": "escapes source_root",
        "hash": "source_sha256 mismatch",
    }[failure]
    with pytest.raises(ValueError, match=expected):
        _run(
            [manifest],
            tmp_path / "output",
            canonical=canonical,
            join=join,
            source_root=source_root,
        )


def test_outputs_are_byte_reproducible_across_output_directories(
    tmp_path: Path,
) -> None:
    inputs, canonical, join, source_root, _ = _valid_fixture(tmp_path)
    output_a = tmp_path / "run-a"
    output_b = tmp_path / "run-b"
    _run(
        inputs,
        output_a,
        canonical=canonical,
        join=join,
        source_root=source_root,
    )
    _run(
        list(reversed(inputs)),
        output_b,
        canonical=canonical,
        join=join,
        source_root=source_root,
    )

    assert {path.name for path in output_a.iterdir()} == {
        "source_exclusion_authority.jsonl",
        "exclusion_selection.jsonl",
        "exclusion_provenance.jsonl",
        "non_selector_compatible_sources.jsonl",
        "summary.json",
        "report.md",
        "hash_ledger.json",
    }
    assert {path.name for path in output_a.iterdir()} == {
        path.name for path in output_b.iterdir()
    }
    assert all(
        (output_a / path.name).read_bytes() == (output_b / path.name).read_bytes()
        for path in output_a.iterdir()
    )
