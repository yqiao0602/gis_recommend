import hashlib
import json
from pathlib import Path

from scripts.prove_qgis_operator_alias_bindings import prove


def _source(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _row(path: Path, operator: str, span: dict, entrypoint: str, status: str = "source_verified_ast") -> dict:
    return {
        "record_id": f"r-{operator}",
        "status": status,
        "source_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema": "gis_recommend.qgis_processing_operator_evidence_sidecar.v1",
        "calls": [
            {
                "operator_id": operator,
                "entrypoint": entrypoint,
                "source_expression": "processing.run('%s', params)" % operator,
                "source_span": span,
            }
        ],
    }


MAPPING = {"native:buffer": "L3_02_01_01", "native:clip": "L3_02_02_06"}


def test_proves_run_and_runalg_alias_forms(tmp_path: Path) -> None:
    run = _source(
        tmp_path / "a.py",
        "import processing\nprocessing.run('qgis:buffer', {'INPUT': layer})\n",
    )
    runalg = _source(
        tmp_path / "b.py",
        "import processing\nprocessing.runalg('qgis:clip', layer, mask, out)\n",
    )
    rows = [
        _row(run, "qgis:buffer", {"line_start": 2, "column_start": 0}, "run"),
        _row(runalg, "qgis:clip", {"line_start": 2, "column_start": 0}, "runalg"),
    ]
    proofs, failures, summary = prove(rows, MAPPING)
    assert not failures
    assert [proof["status"] for proof in proofs] == ["verified_exact_same_slug"] * 2
    assert proofs[0]["canonical_operator"] == "native:buffer"
    assert proofs[0]["l3_via_canonical"] == "L3_02_01_01"
    assert proofs[1]["entrypoint"] == "runalg"
    assert summary["candidate_rows"] == 2
    assert summary["verified_rows"] == 2


def test_skips_native_literals_and_unmapped_slugs(tmp_path: Path) -> None:
    native = _source(
        tmp_path / "a.py",
        "import processing\nprocessing.run('native:buffer', {'INPUT': layer})\n",
    )
    unmapped = _source(
        tmp_path / "b.py",
        "import processing\nprocessing.run('qgis:filedownloader', {'URL': u})\n",
    )
    rows = [
        _row(native, "native:buffer", {"line_start": 2, "column_start": 0}, "run"),
        _row(unmapped, "qgis:filedownloader", {"line_start": 2, "column_start": 0}, "run"),
    ]
    proofs, failures, summary = prove(rows, MAPPING)
    assert not proofs and not failures
    assert summary["candidate_rows"] == 0


def test_fails_closed_on_sha_and_span_and_entrypoint(tmp_path: Path) -> None:
    sha_bad = _source(tmp_path / "a.py", "import processing\nprocessing.run('qgis:buffer', {})\n")
    span_bad = _source(tmp_path / "b.py", "import processing\nprocessing.run('qgis:clip', {})\n")
    entry_bad = _source(tmp_path / "c.py", "import processing\nprocessing.run('qgis:buffer', {})\n")
    rows = [
        {**_row(sha_bad, "qgis:buffer", {"line_start": 2, "column_start": 0}, "run"), "source_sha256": "0" * 64},
        _row(span_bad, "qgis:clip", {"line_start": 5, "column_start": 0}, "run"),
        _row(entry_bad, "qgis:buffer", {"line_start": 2, "column_start": 0}, "runAndLoadResults"),
    ]
    proofs, failures, summary = prove(rows, MAPPING)
    assert not proofs
    assert [failure["reason"] for failure in failures] == [
        "source_sha256_mismatch",
        "call_not_found_at_recorded_span",
        "entrypoint_mismatch:run",
    ]
    assert summary["verified_rows"] == 0


def test_unverified_sidecar_rows_are_not_candidates(tmp_path: Path) -> None:
    source = _source(tmp_path / "a.py", "import processing\nprocessing.run('qgis:buffer', {})\n")
    rows = [_row(source, "qgis:buffer", {"line_start": 2, "column_start": 0}, "run", status="deferred")]
    proofs, failures, summary = prove(rows, MAPPING)
    assert not proofs and not failures
    assert summary["candidate_rows"] == 0
    assert json.dumps(summary)  # summary stays serializable
