import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from gis_recommend.data.gee_workflow_dag_gate import OutputWorkflowDag
from scripts.build_gee_workflow_fidelity_calibration import (
    build_fidelity_calibration,
)


def _write_jsonl(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _workflow(
    *,
    workflow_id: str = "output-workflow-1",
    sink_root_id: str = "sink@10:1",
    sink_line: int = 10,
    status: str = "passed",
    reasons=(),
) -> dict:
    return asdict(
        OutputWorkflowDag(
            workflow_id=workflow_id,
            sink_root_id=sink_root_id,
            sink_line=sink_line,
            definition_ids=("result@1",),
            dependency_edges=(),
            core_call_ordinals=(0, 1),
            core_raw_callees=("source.mean", "source.mean.clip"),
            external_input_identifiers=("geometry",),
            unresolved_identifiers=(),
            status=status,
            fail_closed_reasons=tuple(reasons),
        )
    )


def _source_row(source_sha256: str, workflows: list[dict]) -> dict:
    return {
        "record_key": f"record-{source_sha256[:8]}",
        "source_path": f"data10000/{source_sha256[:8]}.txt",
        "source_sha256": source_sha256,
        "size_bytes": 500,
        "facts_supported": True,
        "calibration_stratum": "linear_export",
        "source_status": "passed",
        "source_fail_closed_reasons": [],
        "slicer_quality_flags": [],
        "extractor_version": "test-v1",
        "workflows": workflows,
        "training_admission": "not_granted_dag_calibration_only",
        "training_rows_emitted": 0,
    }


def _literal(value):
    return {"type": "Literal", "value": value}


def _ident(name):
    return {"type": "Identifier", "name": name}


def _member(obj, prop):
    return {
        "type": "MemberExpression",
        "computed": False,
        "object": obj,
        "property": _ident(prop),
    }


def _call(callee, *arguments):
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def _located(node, start_line, end_line=None):
    return {
        **node,
        "loc": {
            "start": {"line": start_line, "column": 0},
            "end": {"line": end_line or start_line, "column": 80},
        },
    }


def _var(name, init, start_line, end_line=None):
    return _located(
        {
            "type": "VariableDeclaration",
            "declarations": [
                {"type": "VariableDeclarator", "id": _ident(name), "init": init}
            ],
        },
        start_line,
        end_line,
    )


def _mismatch_ast():
    selected = _call(
        _member(
            _call(_member(_ident("ee"), "ImageCollection"), _literal("MODIS")), "select"
        ),
        _literal("LST_Night_1km"),
    )
    callback = {
        "type": "FunctionExpression",
        "params": [_ident("img")],
        "body": {
            "type": "BlockStatement",
            "body": [
                {
                    "type": "ReturnStatement",
                    "argument": _call(
                        _member(_ident("img"), "rename"), _literal("lst")
                    ),
                }
            ],
        },
    }
    later_select = _located(
        _call(_member(_ident("result"), "select"), _literal("scale")), 9
    )
    return {
        "type": "Program",
        "body": [
            _var("result", _call(_member(selected, "map"), callback), 1, 5),
            _located(
                {
                    "type": "ExpressionStatement",
                    "expression": later_select,
                },
                9,
            ),
        ],
    }


class GeeWorkflowFidelityCalibrationTests(unittest.TestCase):
    def _fixture(self, root: Path):
        ast_dir = root / "ast"
        ast_dir.mkdir()
        source_a = "a" * 64
        source_b = "b" * 64
        source_c = "c" * 64
        duplicate = _workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
        )
        mismatch = _workflow(sink_line=9)
        rejected = _workflow(
            status="fail_closed",
            reasons=("unresolved_dependency",),
        )
        rows = [
            _source_row(source_a, [_workflow(), duplicate]),
            _source_row(source_b, [mismatch]),
            _source_row(source_c, [rejected]),
        ]
        workflow_dags = root / "workflow_dags.jsonl"
        _write_jsonl(workflow_dags, rows)
        (ast_dir / f"{source_a}.json").write_text(
            json.dumps({"type": "Program", "body": []}), encoding="utf-8"
        )
        (ast_dir / f"{source_b}.json").write_text(
            json.dumps(_mismatch_ast()), encoding="utf-8"
        )
        (ast_dir / f"{source_c}.json").write_text(
            json.dumps({"type": "Program", "body": []}), encoding="utf-8"
        )
        return workflow_dags, ast_dir

    def test_builder_emits_deterministic_separated_non_training_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflow_dags, ast_dir = self._fixture(root)
            output_dirs = [root / "run-a", root / "run-b"]

            summaries = [
                build_fidelity_calibration(
                    workflow_dags_path=workflow_dags,
                    ast_dir=ast_dir,
                    output_dir=output_dir,
                )
                for output_dir in output_dirs
            ]

            self.assertEqual(summaries[0], summaries[1])
            self.assertEqual(summaries[0]["source_count"], 3)
            self.assertEqual(summaries[0]["workflow_count"], 4)
            self.assertEqual(
                summaries[0]["fidelity_statuses"],
                {"duplicate": 1, "fail_closed": 2, "passed": 1},
            )
            self.assertEqual(summaries[0]["accepted_candidate_count"], 1)
            self.assertEqual(summaries[0]["training_rows_emitted"], 0)

            artifact_names = (
                "fidelity_decisions.jsonl",
                "accepted_candidates.jsonl",
                "rejected_ledger.jsonl",
                "duplicate_ledger.jsonl",
                "summary.json",
                "report.md",
                "hash_ledger.json",
            )
            for artifact_name in artifact_names:
                self.assertEqual(
                    (output_dirs[0] / artifact_name).read_bytes(),
                    (output_dirs[1] / artifact_name).read_bytes(),
                )

            accepted = [
                json.loads(line)
                for line in (output_dirs[0] / "accepted_candidates.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(len(accepted), 1)
            self.assertEqual(
                accepted[0]["training_admission"],
                "not_granted_taxonomy_and_task_text_pending",
            )
            self.assertEqual(accepted[0]["training_rows_emitted"], 0)
            rejected = (output_dirs[0] / "rejected_ledger.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertIn("static_single_band_map_output_mismatch", rejected)
            self.assertIn("upstream_dag_not_passed", rejected)

            ledger = json.loads(
                (output_dirs[0] / "hash_ledger.json").read_text(encoding="utf-8")
            )
            self.assertEqual(ledger["schema"], "gis_recommend.hash_ledger.v1")
            self.assertEqual(
                ledger["inputs"]["workflow_dags"]["sha256"],
                hashlib.sha256(workflow_dags.read_bytes()).hexdigest(),
            )
            self.assertNotIn("hash_ledger.json", ledger["artifacts"])

    def test_builder_fails_closed_on_invalid_source_workflow_and_ast_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflow_dags, ast_dir = self._fixture(root)
            rows = [json.loads(line) for line in workflow_dags.read_text().splitlines()]

            bad_sha = [dict(rows[0], source_sha256="not-a-sha")]
            _write_jsonl(workflow_dags, bad_sha)
            with self.assertRaisesRegex(ValueError, "source_sha256"):
                build_fidelity_calibration(workflow_dags, ast_dir, root / "bad-sha")

            malformed = _source_row("d" * 64, [_workflow()])
            malformed["workflows"][0]["unexpected"] = True
            _write_jsonl(workflow_dags, [malformed])
            (ast_dir / f"{'d' * 64}.json").write_text(
                json.dumps({"type": "Program", "body": []}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "workflow schema"):
                build_fidelity_calibration(workflow_dags, ast_dir, root / "bad-schema")

            invalid_status = _source_row("e" * 64, [_workflow(status="unknown")])
            _write_jsonl(workflow_dags, [invalid_status])
            (ast_dir / f"{'e' * 64}.json").write_text(
                json.dumps({"type": "Program", "body": []}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "workflow status"):
                build_fidelity_calibration(workflow_dags, ast_dir, root / "bad-status")

            missing_ast = _source_row("f" * 64, [_workflow()])
            _write_jsonl(workflow_dags, [missing_ast])
            with self.assertRaisesRegex(ValueError, "missing AST"):
                build_fidelity_calibration(workflow_dags, ast_dir, root / "missing-ast")


if __name__ == "__main__":
    unittest.main()
