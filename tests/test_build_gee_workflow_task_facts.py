import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_gee_workflow_task_facts import build_workflow_task_facts
from test_gee_workflow_task_facts import fixture


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeWorkflowTaskFactsBuilderTests(unittest.TestCase):
    def test_builds_reproducible_partition_with_composite_workflow_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            ast_dir = root / "ast"
            source_root.mkdir()
            ast_dir.mkdir()
            source_path = source_root / "data10000" / "script_1.txt"
            source_path.parent.mkdir()
            source_path.write_text("// frozen source\n", encoding="utf-8")
            source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()

            typed, fidelity, ast = fixture()
            typed["source_sha256"] = source_sha
            fidelity["source_sha256"] = source_sha
            second_typed = json.loads(json.dumps(typed))
            second_fidelity = json.loads(json.dumps(fidelity))
            second_typed["workflow_id"] = "output-workflow-2"
            second_fidelity["workflow_id"] = "output-workflow-2"
            second_fidelity["sink_root_id"] = "sink@5:2"
            ast_path = ast_dir / f"{source_sha}.ast.json"
            ast_path.write_text(json.dumps(ast, sort_keys=True), encoding="utf-8")

            typed_path = root / "typed.jsonl"
            fidelity_path = root / "fidelity.jsonl"
            write_jsonl(typed_path, [typed, second_typed])
            write_jsonl(fidelity_path, [fidelity, second_fidelity])

            outputs = []
            for name in ("out-a", "out-b"):
                output_dir = root / name
                summary = build_workflow_task_facts(
                    typed_candidates_path=typed_path,
                    fidelity_candidates_path=fidelity_path,
                    ast_dir=ast_dir,
                    source_root=source_root,
                    output_dir=output_dir,
                    review_limit=50,
                )
                self.assertEqual(summary["counts"]["input_mapping_complete"], 2)
                self.assertEqual(summary["counts"]["fact_bundles"], 2)
                self.assertEqual(summary["counts"]["task_text_candidates"], 1)
                self.assertEqual(summary["counts"]["duplicates"], 1)
                self.assertEqual(summary["counts"]["fail_closed"], 0)
                self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
                outputs.append(output_dir)

            names = {
                "workflow_fact_bundles.jsonl",
                "task_text_candidates.jsonl",
                "fact_fail_closed.jsonl",
                "task_text_duplicates.jsonl",
                "risk_review_packet.jsonl",
                "summary.json",
                "report.md",
                "hash_ledger.json",
            }
            self.assertEqual({path.name for path in outputs[0].iterdir()}, names)
            for name in names:
                self.assertEqual(
                    (outputs[0] / name).read_bytes(),
                    (outputs[1] / name).read_bytes(),
                )

            candidates = [
                json.loads(line)
                for line in (outputs[0] / "task_text_candidates.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(candidates[0]["workflow_key"], [source_sha, "output-workflow-1"])
            self.assertEqual(candidates[0]["calibration_stratum"], "linear_export")
            self.assertEqual(candidates[0]["training_admission"], "not_granted_risk_review_and_final_dedup_pending")
            ledger = json.loads((outputs[0] / "hash_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["inputs"]["typed_candidates"]["sha256"],
                hashlib.sha256(typed_path.read_bytes()).hexdigest(),
            )

    def test_missing_fidelity_join_is_fail_closed_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            typed, _, _ = fixture()
            typed_path = root / "typed.jsonl"
            fidelity_path = root / "fidelity.jsonl"
            write_jsonl(typed_path, [typed])
            write_jsonl(fidelity_path, [])
            ast_dir = root / "ast"
            source_root = root / "source"
            ast_dir.mkdir()
            source_root.mkdir()

            summary = build_workflow_task_facts(
                typed_candidates_path=typed_path,
                fidelity_candidates_path=fidelity_path,
                ast_dir=ast_dir,
                source_root=source_root,
                output_dir=root / "out",
            )

            self.assertEqual(summary["counts"]["fail_closed"], 1)
            failure = json.loads(
                (root / "out" / "fact_fail_closed.jsonl").read_text(encoding="utf-8")
            )
            self.assertEqual(failure["reason"], "missing_fidelity_join")

    def test_ledger_is_stable_when_replay_ast_directory_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            source_path = source_root / "data10000" / "script_1.txt"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("// frozen source\n", encoding="utf-8")
            source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
            typed, fidelity, ast = fixture()
            typed["source_sha256"] = source_sha
            fidelity["source_sha256"] = source_sha
            typed_path = root / "typed.jsonl"
            fidelity_path = root / "fidelity.jsonl"
            write_jsonl(typed_path, [typed])
            write_jsonl(fidelity_path, [fidelity])

            outputs = []
            for name in ("replay-a", "replay-b"):
                ast_dir = root / name / "ast"
                ast_dir.mkdir(parents=True)
                (ast_dir / f"{source_sha}.ast.json").write_text(
                    json.dumps(ast, sort_keys=True), encoding="utf-8"
                )
                output_dir = root / name / "out"
                build_workflow_task_facts(
                    typed_candidates_path=typed_path,
                    fidelity_candidates_path=fidelity_path,
                    ast_dir=ast_dir,
                    source_root=source_root,
                    output_dir=output_dir,
                )
                outputs.append(output_dir)

            for name in (
                "workflow_fact_bundles.jsonl",
                "task_text_candidates.jsonl",
                "fact_fail_closed.jsonl",
                "task_text_duplicates.jsonl",
                "risk_review_packet.jsonl",
                "summary.json",
                "report.md",
                "hash_ledger.json",
            ):
                self.assertEqual(
                    (outputs[0] / name).read_bytes(),
                    (outputs[1] / name).read_bytes(),
                )

            ledger = json.loads((outputs[0] / "hash_ledger.json").read_text(encoding="utf-8"))
            verified = ledger["inputs"]["verified_source_and_ast_files"]
            self.assertEqual(
                set(verified),
                {"source/data10000/script_1.txt", f"ast/{source_sha}.json"},
            )


if __name__ == "__main__":
    unittest.main()
