from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/replay_qgis_snap_split_proposal.py"
SPEC = importlib.util.spec_from_file_location("replay_qgis_snap_split_proposal", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_replays_only_snap_split_parents_as_proposal_only(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        """def first(layer):
    return processing.run('native:snapgeometries', {'INPUT': layer})['OUTPUT']

def second(layer):
    snapped = processing.run('native:snapgeometries', {'INPUT': layer})['OUTPUT']
    return processing.run('native:fixgeometries', {'INPUT': snapped})['OUTPUT']
""",
        encoding="utf-8",
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    parent = {
        "record_id": "split",
        "source_path": str(source),
        "source_sha256": digest,
        "source_root_id": "fixture",
        "action": "split_subworkflow",
        "rule_id": "split-disconnected-scopes-v1",
        "signature_hash": "sig",
        "call_sites": [
            {"operator_id": "native:snapgeometries", "line_start": 2, "line_end": 2},
            {"operator_id": "native:snapgeometries", "line_start": 5, "line_end": 5},
            {"operator_id": "native:fixgeometries", "line_start": 6, "line_end": 6},
        ],
        "mapped_l3_chain": ["L3_02_07_09", "L3_02_07_09", "L3_01_05_02"],
    }

    rows, summary = MODULE.build_snap_split_units([parent])

    assert summary["parent_rows"] == 1
    assert summary["multi_step_units"] == 1
    assert summary["training_rows_emitted"] == 0
    assert all(row["proposal_only"] for row in rows)
    assert all(not row["training_row_emitted"] for row in rows)
