from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.build_qgis_api_source_disjoint_gate import (
    assign_alias_groups,
    rebase_and_adjudicate,
    split_alias_groups,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unit(
    path: Path,
    *,
    declared_authority: str,
    candidate_id: str,
    unit_id: str,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "unit_id": unit_id,
        "record_id": f"record-{candidate_id}",
        "source_authority_key": declared_authority,
        "normalized_source_body_sha256": declared_authority.rsplit(":", 1)[-1],
        "source_sha256": _sha256(path),
        "source_path": str(path),
        "source_root_id": "fixture",
        "source_span": [1, 2],
        "steps": [],
        "dependency_edges": [],
        "training_row_emitted": False,
    }


def _decision(authority: str, *, accepted: bool = True) -> dict[str, str]:
    return {
        "declared_source_authority_key": authority,
        "task_boundary_decision": "true_positive" if accepted else "false_positive",
        "dependency_decision": "complete" if accepted else "truncated",
        "terminal_decision": "complete",
        "failure_labels": "" if accepted else "upstream_dependency_missing",
        "reviewer_notes": "reviewed",
    }


class QgisApiSourceDisjointGateTest(unittest.TestCase):
    def test_rebases_extended_header_aliases_and_defers_review_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            body = 'processing.run("native:centroids", {})\n'
            bare = root / "bare.py"
            harvested = root / "harvested.py"
            rejected = root / "rejected.py"
            bare.write_text(body, encoding="utf-8")
            harvested.write_text(
                "# Source repo: owner/repo\n"
                "# Source path: workflow.py\n"
                "# Source kind: python_file\n"
                "# Code block id: whole_file\n"
                "# Harvested at: now\n\n"
                + body,
                encoding="utf-8",
            )
            rejected.write_text("value = 1\n", encoding="utf-8")
            rows = [
                _unit(
                    bare,
                    declared_authority="normalized_source_body_sha256:bare",
                    candidate_id="bare",
                    unit_id="shared",
                ),
                _unit(
                    harvested,
                    declared_authority="normalized_source_body_sha256:harvested",
                    candidate_id="harvested",
                    unit_id="shared",
                ),
                _unit(
                    rejected,
                    declared_authority="normalized_source_body_sha256:rejected",
                    candidate_id="rejected",
                    unit_id="rejected-unit",
                ),
            ]
            decisions = [
                _decision("normalized_source_body_sha256:bare"),
                _decision("normalized_source_body_sha256:harvested"),
                _decision(
                    "normalized_source_body_sha256:rejected", accepted=False
                ),
            ]

            accepted, deferred, summary = rebase_and_adjudicate(rows, decisions)

            self.assertEqual(len(accepted), 2)
            self.assertEqual(len(deferred), 1)
            self.assertEqual(
                accepted[0]["source_authority_key"],
                accepted[1]["source_authority_key"],
            )
            self.assertEqual(summary["rebased_source_authorities"], 2)
            self.assertEqual(summary["accepted_units"], 2)
            self.assertEqual(summary["deferred_units"], 1)

    def test_requires_review_coverage_for_every_declared_authority(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text("value = 1\n", encoding="utf-8")
            rows = [
                _unit(
                    path,
                    declared_authority="normalized_source_body_sha256:missing",
                    candidate_id="candidate",
                    unit_id="unit",
                )
            ]

            with self.assertRaisesRegex(ValueError, "review coverage"):
                rebase_and_adjudicate(rows, [])

    def test_shared_terminal_dag_aliases_never_cross_split(self) -> None:
        rows = []
        for authority, unit_ids in {
            "authority-a": ["shared-1", "a-only"],
            "authority-b": ["shared-1", "b-only"],
            "authority-c": ["c-only"],
            "authority-d": ["d-only"],
        }.items():
            for ordinal, unit_id in enumerate(unit_ids):
                rows.append(
                    {
                        "candidate_id": f"{authority}-{ordinal}",
                        "unit_id": unit_id,
                        "source_authority_key": authority,
                        "source_sha256": f"sha-{authority}",
                        "training_row_emitted": False,
                    }
                )

        grouped, group_summary = assign_alias_groups(rows)
        calibration, holdout, split_summary = split_alias_groups(grouped, seed=7)

        split_by_authority = {
            row["source_authority_key"]: row["review_split"]
            for row in calibration + holdout
        }
        self.assertEqual(split_by_authority["authority-a"], split_by_authority["authority-b"])
        self.assertEqual(group_summary["source_authorities"], 4)
        self.assertEqual(group_summary["alias_groups"], 3)
        self.assertEqual(split_summary["source_authority_overlap"], 0)
        self.assertEqual(split_summary["unit_id_overlap"], 0)


if __name__ == "__main__":
    unittest.main()
