import unittest
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from scripts.build_gee_workflow_dag_calibration import (
    _load_fixed_selection_records,
    _select_authority_candidates,
    _validate_selected_quotas,
    build_calibration,
    main,
    select_calibration_candidates,
)


def row(source_hash, source_text, *, facts_supported=True, size_bytes=None):
    source_text = source_text + " " * max(0, 220 - len(source_text.encode("utf-8")))
    return {
        "record_key": f"data10000/script_{source_hash[:4]}.txt",
        "source_path": f"data10000/script_{source_hash[:4]}.txt",
        "source_sha256": source_hash,
        "source_text": source_text,
        "size_bytes": (
            len(source_text.encode("utf-8")) if size_bytes is None else size_bytes
        ),
        "facts_supported": facts_supported,
    }


class GeeWorkflowDagCalibrationSelectionTests(unittest.TestCase):
    def test_selects_source_disjoint_strata_deterministically(self):
        linear = row(
            "1" * 64,
            "var x = ee.Image('S2').clip(roi); Export.image.toDrive({image: x});",
        )
        helper = row(
            "2" * 64,
            "function mask(x) { return x.selfMask(); }\n"
            "var y = ee.Image('S2').map(mask); Export.image.toDrive({image: y});",
        )
        control = row(
            "3" * 64,
            "var x = ee.Image('S2'); if (ready) { x = x.clip(roi); } "
            "Export.image.toDrive({image: x});",
        )

        selected = select_calibration_candidates(
            [control, linear, helper],
            quotas={"linear_export": 1, "helper_export": 1, "control_flow_export": 1},
        )

        self.assertEqual(
            [(item["calibration_stratum"], item["source_sha256"]) for item in selected],
            [
                ("linear_export", "1" * 64),
                ("helper_export", "2" * 64),
                ("control_flow_export", "3" * 64),
            ],
        )
        self.assertTrue(all("source_text" not in item for item in selected))

    def test_selection_excludes_fixed_calibration_source_hashes(self):
        first = row(
            "1" * 64,
            "var x = ee.Image('S2'); Export.image.toDrive({image: x});",
        )
        second = row(
            "2" * 64,
            "var y = ee.Image('S2'); Export.image.toDrive({image: y});",
        )

        selected = select_calibration_candidates(
            [first, second],
            quotas={"linear_export": 1, "helper_export": 0, "control_flow_export": 0},
            exclude_source_sha256={first["source_sha256"]},
        )

        self.assertEqual([item["source_sha256"] for item in selected], ["2" * 64])

    def test_exact_quota_validation_fails_before_pilot_parsing(self):
        selected = [
            {
                "source_sha256": "1" * 64,
                "calibration_stratum": "linear_export",
            }
        ]

        with self.assertRaisesRegex(ValueError, "exact selection quotas"):
            _validate_selected_quotas(
                selected,
                {"linear_export": 2, "helper_export": 0, "control_flow_export": 0},
            )

    def test_streaming_authority_selection_stops_after_exact_quota_and_exclusion(self):
        source_texts = [
            "var x = ee.Image('S2'); Export.image.toDrive({image: x});",
            "var y = ee.Image('S2'); Export.image.toDrive({image: y});",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "sources"
            records = []
            for index, source_text in enumerate(source_texts, start=1):
                padded = source_text + " " * max(
                    0, 220 - len(source_text.encode("utf-8"))
                )
                path = source_root / "data10000" / f"script_{index}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(padded, encoding="utf-8")
                records.append(
                    {
                        "record_key": f"data10000/script_{index}.txt",
                        "source_path": f"data10000/script_{index}.txt",
                        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "instances": [{"source_path": f"data10000/script_{index}.txt"}],
                    }
                )
            records.sort(key=lambda row: row["source_sha256"])
            missing_path = "data10000/script_missing.txt"
            records.append(
                {
                    "record_key": missing_path,
                    "source_path": missing_path,
                    "source_sha256": "f" * 64,
                    "instances": [{"source_path": missing_path}],
                }
            )
            canonical_manifest = root / "canonical_sources.jsonl"
            canonical_manifest.write_text(
                "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
            )
            join_paths = {row["source_path"] for row in records}

            selected = _select_authority_candidates(
                canonical_manifest,
                source_root,
                join_paths,
                quotas={
                    "linear_export": 1,
                    "helper_export": 0,
                    "control_flow_export": 0,
                },
                exclude_source_sha256={records[0]["source_sha256"]},
            )

            self.assertEqual(
                [row["source_sha256"] for row in selected],
                [records[1]["source_sha256"]],
            )

    def test_excludes_rows_without_exact_facts_export_or_gee_structure(self):
        selected = select_calibration_candidates(
            [
                row("1" * 64, "var x = ee.Image('S2'); Map.addLayer(x);"),
                row(
                    "2" * 64,
                    "var x = ee.Image('S2'); Export.image.toDrive({image: x});",
                    facts_supported=False,
                ),
                row("3" * 64, "Export.table.toDrive({collection: rows});"),
                row(
                    "4" * 64,
                    "var x = ee.Image('S2'); Export.image.toDrive({image: x});",
                ),
            ],
            quotas={"linear_export": 2, "helper_export": 0, "control_flow_export": 0},
        )

        self.assertEqual([item["source_sha256"] for item in selected], ["4" * 64])

    def test_duplicate_source_hash_is_rejected(self):
        duplicate = row(
            "a" * 64,
            "var x = ee.Image('S2'); Export.image.toDrive({image: x});",
        )

        with self.assertRaisesRegex(ValueError, "duplicate source_sha256"):
            select_calibration_candidates(
                [duplicate, dict(duplicate)],
                quotas={
                    "linear_export": 1,
                    "helper_export": 0,
                    "control_flow_export": 0,
                },
            )

    def test_build_calibration_runs_real_parser_extractor_and_dag_gate(self):
        source = (
            "var roi = ee.Geometry.Point([0, 0]);\n"
            "var source = ee.ImageCollection('COPERNICUS/S2');\n"
            "var filtered = source.filterBounds(roi);\n"
            "var result = filtered.mean().clip(roi);\n"
            "Export.image.toDrive({image: result, description: 'result'});\n"
        )
        source += " " * max(0, 220 - len(source.encode("utf-8")))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "sources"
            source_path = source_root / "data10000" / "script_10.txt"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(source, encoding="utf-8")
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            canonical_manifest = root / "canonical_sources.jsonl"
            canonical_manifest.write_text(
                json.dumps(
                    {
                        "record_key": "data10000/script_10.txt",
                        "source_path": "data10000/script_10.txt",
                        "source_sha256": source_hash,
                        "instances": [{"source_path": "data10000/script_10.txt"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            join_ledger = root / "join_ledger.jsonl"
            join_ledger.write_text(
                json.dumps(
                    {
                        "join_status": "authoritative_exact_batch_join",
                        "source_path": "data10000/script_10.txt",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            exclude_selection_manifest = root / "exclude_selection.jsonl"
            exclude_selection_manifest.write_text("{}\n", encoding="utf-8")
            output_dir = root / "output"

            with (
                patch(
                    "scripts.build_gee_workflow_dag_calibration._validate_selected_quotas",
                    wraps=_validate_selected_quotas,
                ) as validate_quotas,
                patch(
                    "scripts.build_gee_workflow_dag_calibration._load_fixed_selection_records",
                    return_value=[{"source_sha256": "0" * 64}],
                ),
            ):
                summary = build_calibration(
                    canonical_manifest=canonical_manifest,
                    join_ledger=join_ledger,
                    source_root=source_root,
                    parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                    output_dir=output_dir,
                    exclude_selection_manifest=exclude_selection_manifest,
                    node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
                    quotas={
                        "linear_export": 1,
                        "helper_export": 0,
                        "control_flow_export": 0,
                    },
                )

            validate_quotas.assert_called_once()
            self.assertEqual(summary["selected_source_count"], 1)
            self.assertEqual(summary["source_statuses"], {"passed": 1})
            self.assertEqual(summary["training_rows_emitted"], 0)
            self.assertTrue((output_dir / "workflow_dags.jsonl").is_file())
            ledger = json.loads(
                (output_dir / "hash_ledger.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                ledger["inputs"]["exclude_selection_manifest"]["sha256"],
                hashlib.sha256(exclude_selection_manifest.read_bytes()).hexdigest(),
            )


class GeeWorkflowDagCalibrationFixedReplayTests(unittest.TestCase):
    SOURCE = (
        "var roi = ee.Geometry.Point([0, 0]);\n"
        "var source = ee.ImageCollection('COPERNICUS/S2');\n"
        "var result = source.mean().clip(roi);\n"
        "Export.image.toDrive({image: result, description: 'result'});\n"
    )

    def _fixture(self, root: Path, *, source_text: str | None = None):
        source_root = root / "sources"
        source_path = source_root / "data10000" / "script_10.txt"
        source_path.parent.mkdir(parents=True)
        source = self.SOURCE if source_text is None else source_text
        source += " " * max(0, 220 - len(source.encode("utf-8")))
        source_path.write_text(source, encoding="utf-8")
        source_bytes = source_path.read_bytes()
        selection_row = {
            "record_key": "data10000/script_10.txt",
            "source_path": "data10000/script_10.txt",
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "size_bytes": len(source_bytes),
            "facts_supported": True,
            "calibration_stratum": "linear_export",
        }
        selection_manifest = root / "selection.jsonl"
        selection_manifest.write_text(
            json.dumps(selection_row) + "\n", encoding="utf-8"
        )
        return source_root, selection_manifest, selection_row

    def _rewrite_selection(self, path: Path, rows):
        path.write_text(
            "".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8"
        )

    def test_fixed_replay_succeeds_without_canonical_or_join_manifests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            output_dir = root / "output"

            try:
                summary = build_calibration(
                    canonical_manifest=root / "missing-canonical.jsonl",
                    join_ledger=root / "missing-join.jsonl",
                    selection_manifest=selection_manifest,
                    source_root=source_root,
                    parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                    output_dir=output_dir,
                    node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
                )
            except ValueError as exc:
                self.fail(
                    f"fixed selection mode read or rejected unrelated authority paths: {exc}"
                )

            self.assertEqual(summary["selected_source_count"], 1)
            self.assertEqual(summary["source_statuses"], {"passed": 1})
            emitted_selection = [
                json.loads(line)
                for line in (output_dir / "selection.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(emitted_selection, [selection_row])
            self.assertNotIn("source_text", emitted_selection[0])
            ledger_inputs = json.loads(
                (output_dir / "hash_ledger.json").read_text(encoding="utf-8")
            )["inputs"]
            self.assertEqual(set(ledger_inputs), {"selection_manifest", "parser"})
            self.assertEqual(
                ledger_inputs["selection_manifest"]["path"], "selection.jsonl"
            )

    def test_fixed_loader_preserves_order_and_retains_only_resolved_internal_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, first = self._fixture(root)
            second_path = source_root / "data10000" / "script_20.txt"
            second_source = self.SOURCE + "// second\n"
            second_source += " " * max(0, 220 - len(second_source.encode("utf-8")))
            second_path.write_text(second_source, encoding="utf-8")
            second_bytes = second_path.read_bytes()
            second = {
                **first,
                "record_key": "data10000/script_20.txt",
                "source_path": "data10000/script_20.txt",
                "source_sha256": hashlib.sha256(second_bytes).hexdigest(),
                "size_bytes": len(second_bytes),
                "calibration_stratum": "helper_export",
            }
            self._rewrite_selection(selection_manifest, [second, first])

            loaded = _load_fixed_selection_records(selection_manifest, source_root)

            self.assertEqual(
                [item["source_sha256"] for item in loaded],
                [second["source_sha256"], first["source_sha256"]],
            )
            self.assertNotIn("source_text", loaded[0])
            self.assertEqual(loaded[0]["_resolved_source_path"], second_path.resolve())

    def test_fixed_loader_enforces_source_size_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            source_path = source_root / selection_row["source_path"]
            for size_bytes in (199, 100_001):
                with self.subTest(size_bytes=size_bytes):
                    source_bytes = b"x" * size_bytes
                    source_path.write_bytes(source_bytes)
                    bounded_row = {
                        **selection_row,
                        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                        "size_bytes": size_bytes,
                    }
                    self._rewrite_selection(selection_manifest, [bounded_row])
                    with self.assertRaisesRegex(ValueError, "between 200 and 100000"):
                        _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_replay_parses_a_verified_private_source_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            original_source = (source_root / selection_row["source_path"]).resolve()
            marker = root / "parser_source_path.txt"
            wrapper = root / "parser_wrapper.py"
            real_node = os.environ.get("GEE_NODE_EXECUTABLE", "node")
            real_parser = Path("scripts/parse_gee_js_with_locations.js").resolve()
            wrapper.write_text(
                "import pathlib\n"
                "import subprocess\n"
                "import sys\n"
                f"pathlib.Path({str(marker)!r}).write_text(sys.argv[1], encoding='utf-8')\n"
                f"raise SystemExit(subprocess.run([{real_node!r}, {str(real_parser)!r}, "
                "sys.argv[1], sys.argv[2]], check=False).returncode)\n",
                encoding="utf-8",
            )

            summary = build_calibration(
                canonical_manifest=None,
                join_ledger=None,
                selection_manifest=selection_manifest,
                source_root=source_root,
                parser_path=wrapper,
                output_dir=root / "output",
                node_executable=sys.executable,
            )

            parsed_source = Path(marker.read_text(encoding="utf-8"))
            self.assertEqual(summary["source_statuses"], {"passed": 1})
            self.assertNotEqual(parsed_source, original_source)
            self.assertFalse(parsed_source.exists())

    def test_fixed_replay_core_artifacts_are_byte_identical_across_output_dirs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, _ = self._fixture(root)
            output_dirs = [root / "output-a", root / "output-b"]
            for output_dir in output_dirs:
                build_calibration(
                    canonical_manifest=None,
                    join_ledger=None,
                    selection_manifest=selection_manifest,
                    source_root=source_root,
                    parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                    output_dir=output_dir,
                    node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
                )

            for artifact in (
                "selection.jsonl",
                "workflow_dags.jsonl",
                "parse_failures.jsonl",
                "summary.json",
                "report.md",
            ):
                with self.subTest(artifact=artifact):
                    self.assertEqual(
                        (output_dirs[0] / artifact).read_bytes(),
                        (output_dirs[1] / artifact).read_bytes(),
                    )

    def test_frozen_ast_replay_does_not_require_node_and_preserves_core_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, _ = self._fixture(root)
            parsed_output = root / "parsed"
            replayed_output = root / "replayed"
            build_calibration(
                canonical_manifest=None,
                join_ledger=None,
                selection_manifest=selection_manifest,
                source_root=source_root,
                parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                output_dir=parsed_output,
                node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
            )

            build_calibration(
                canonical_manifest=None,
                join_ledger=None,
                selection_manifest=selection_manifest,
                source_root=source_root,
                parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                output_dir=replayed_output,
                node_executable="node-does-not-exist",
                ast_replay_dir=parsed_output / "ast",
            )

            for artifact in (
                "selection.jsonl",
                "workflow_dags.jsonl",
                "parse_failures.jsonl",
                "summary.json",
                "report.md",
            ):
                with self.subTest(artifact=artifact):
                    self.assertEqual(
                        (parsed_output / artifact).read_bytes(),
                        (replayed_output / artifact).read_bytes(),
                    )
            ledger_inputs = json.loads(
                (replayed_output / "hash_ledger.json").read_text(encoding="utf-8")
            )["inputs"]
            self.assertIn("ast_replay", ledger_inputs)
            self.assertEqual(ledger_inputs["ast_replay"]["file_count"], 1)

    def test_missing_ast_replay_is_byte_identical_across_replay_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            replay_dirs = [root / "replay-a", root / "replay-b"]
            output_dirs = [root / "output-a", root / "output-b"]
            for replay_dir, output_dir in zip(replay_dirs, output_dirs, strict=True):
                replay_dir.mkdir()
                build_calibration(
                    canonical_manifest=None,
                    join_ledger=None,
                    selection_manifest=selection_manifest,
                    source_root=source_root,
                    parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                    output_dir=output_dir,
                    node_executable="node-does-not-exist",
                    ast_replay_dir=replay_dir,
                )

            for artifact in (
                "parse_failures.jsonl",
                "summary.json",
                "report.md",
                "selection.jsonl",
                "workflow_dags.jsonl",
                "hash_ledger.json",
            ):
                with self.subTest(artifact=artifact):
                    self.assertEqual(
                        (output_dirs[0] / artifact).read_bytes(),
                        (output_dirs[1] / artifact).read_bytes(),
                    )
            failure = json.loads(
                (output_dirs[0] / "parse_failures.jsonl").read_text(encoding="utf-8")
            )
            self.assertIn(
                f"ast/{selection_row['source_sha256']}.json",
                failure["parser_stderr"],
            )
            self.assertNotIn(str(replay_dirs[0]), failure["parser_stderr"])

    def test_successful_parser_without_fresh_ast_cannot_reuse_stale_ast(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            output_dir = root / "output"
            build_calibration(
                canonical_manifest=None,
                join_ledger=None,
                selection_manifest=selection_manifest,
                source_root=source_root,
                parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                output_dir=output_dir,
                node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
            )
            ast_path = output_dir / "ast" / f"{selection_row['source_sha256']}.json"
            self.assertTrue(ast_path.is_file())
            fake_parser = root / "successful_no_output_parser.py"
            fake_parser.write_text("raise SystemExit(0)\n", encoding="utf-8")

            summary = build_calibration(
                canonical_manifest=None,
                join_ledger=None,
                selection_manifest=selection_manifest,
                source_root=source_root,
                parser_path=fake_parser,
                output_dir=output_dir,
                node_executable=sys.executable,
            )

            self.assertEqual(summary["ast_success_count"], 0)
            self.assertEqual(summary["ast_failure_count"], 1)
            self.assertEqual((output_dir / "workflow_dags.jsonl").read_bytes(), b"")
            failures = [
                json.loads(line)
                for line in (output_dir / "parse_failures.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["fail_closed_reason"], "ast_parse_failure")
            self.assertEqual(
                sorted(path.name for path in (output_dir / "ast").iterdir()),
                [ast_path.name],
            )

    def test_successful_parser_with_unreadable_ast_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, _ = self._fixture(root)
            fake_parser = root / "invalid_ast_parser.py"
            fake_parser.write_text(
                "import pathlib\n"
                "import sys\n"
                "pathlib.Path(sys.argv[2]).write_text('{', encoding='utf-8')\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            try:
                summary = build_calibration(
                    canonical_manifest=None,
                    join_ledger=None,
                    selection_manifest=selection_manifest,
                    source_root=source_root,
                    parser_path=fake_parser,
                    output_dir=root / "output",
                    node_executable=sys.executable,
                )
            except Exception as exc:
                self.fail(f"unreadable AST should fail closed, not raise: {exc}")

            self.assertEqual(summary["ast_success_count"], 0)
            self.assertEqual(summary["ast_failure_count"], 1)

    def test_syntax_failure_artifacts_are_byte_identical_across_output_dirs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            fake_parser = root / "syntax_error_parser.py"
            fake_parser.write_text(
                "import sys\n"
                "sys.stderr.write(f'SyntaxError in {sys.argv[1]} while writing {sys.argv[2]}')\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            output_dirs = [root / "output-a", root / "output-b"]
            for output_dir in output_dirs:
                build_calibration(
                    canonical_manifest=None,
                    join_ledger=None,
                    selection_manifest=selection_manifest,
                    source_root=source_root,
                    parser_path=fake_parser,
                    output_dir=output_dir,
                    node_executable=sys.executable,
                )

            for artifact in (
                "parse_failures.jsonl",
                "summary.json",
                "report.md",
                "selection.jsonl",
                "workflow_dags.jsonl",
            ):
                with self.subTest(artifact=artifact):
                    self.assertEqual(
                        (output_dirs[0] / artifact).read_bytes(),
                        (output_dirs[1] / artifact).read_bytes(),
                    )
            failure = json.loads(
                (output_dirs[0] / "parse_failures.jsonl").read_text(encoding="utf-8")
            )
            self.assertIn(selection_row["source_path"], failure["parser_stderr"])
            self.assertIn(
                str(Path("ast") / f"{selection_row['source_sha256']}.json"),
                failure["parser_stderr"],
            )
            self.assertNotIn("gee-calibration-source-", failure["parser_stderr"])

    def test_malformed_ast_roots_fail_closed_without_replacing_formal_ast(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, malformed_ast in enumerate(([], {})):
                with self.subTest(malformed_ast=malformed_ast):
                    case_root = root / f"case-{index}"
                    case_root.mkdir()
                    source_root, selection_manifest, selection_row = self._fixture(
                        case_root
                    )
                    output_dir = case_root / "output"
                    build_calibration(
                        canonical_manifest=None,
                        join_ledger=None,
                        selection_manifest=selection_manifest,
                        source_root=source_root,
                        parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                        output_dir=output_dir,
                        node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
                    )
                    ast_path = (
                        output_dir / "ast" / f"{selection_row['source_sha256']}.json"
                    )
                    formal_ast = ast_path.read_bytes()
                    fake_parser = case_root / "malformed_root_parser.py"
                    payload = json.dumps(malformed_ast)
                    fake_parser.write_text(
                        "import pathlib\n"
                        "import sys\n"
                        f"pathlib.Path(sys.argv[2]).write_text({payload!r}, encoding='utf-8')\n",
                        encoding="utf-8",
                    )
                    try:
                        summary = build_calibration(
                            canonical_manifest=None,
                            join_ledger=None,
                            selection_manifest=selection_manifest,
                            source_root=source_root,
                            parser_path=fake_parser,
                            output_dir=output_dir,
                            node_executable=sys.executable,
                        )
                    except Exception as exc:
                        self.fail(
                            f"malformed AST root should fail closed, not raise: {exc}"
                        )

                    self.assertEqual(summary["ast_failure_count"], 1)
                    self.assertEqual(ast_path.read_bytes(), formal_ast)
                    failure = json.loads(
                        (output_dir / "parse_failures.jsonl").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertIn("invalid AST root", failure["parser_stderr"])

    def test_downstream_ast_processing_errors_fail_closed_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            targets = (
                "scripts.build_gee_workflow_dag_calibration.extract_gee_source_evidence",
                "scripts.build_gee_workflow_dag_calibration.build_output_workflow_dags",
            )
            for index, target in enumerate(targets):
                with self.subTest(target=target):
                    case_root = root / f"case-{index}"
                    case_root.mkdir()
                    source_root, selection_manifest, selection_row = self._fixture(
                        case_root
                    )
                    output_dir = case_root / "output"
                    build_calibration(
                        canonical_manifest=None,
                        join_ledger=None,
                        selection_manifest=selection_manifest,
                        source_root=source_root,
                        parser_path=Path("scripts/parse_gee_js_with_locations.js"),
                        output_dir=output_dir,
                        node_executable=os.environ.get("GEE_NODE_EXECUTABLE", "node"),
                    )
                    ast_path = (
                        output_dir / "ast" / f"{selection_row['source_sha256']}.json"
                    )
                    formal_ast = ast_path.read_bytes()
                    fake_parser = case_root / "valid_program_parser.py"
                    fake_parser.write_text(
                        "import json\n"
                        "import pathlib\n"
                        "import sys\n"
                        "pathlib.Path(sys.argv[2]).write_text("
                        "json.dumps({'type': 'Program', 'body': [], 'new': True}), encoding='utf-8')\n",
                        encoding="utf-8",
                    )

                    with patch(
                        target, side_effect=RuntimeError("forced downstream failure")
                    ):
                        try:
                            summary = build_calibration(
                                canonical_manifest=None,
                                join_ledger=None,
                                selection_manifest=selection_manifest,
                                source_root=source_root,
                                parser_path=fake_parser,
                                output_dir=output_dir,
                                node_executable=sys.executable,
                            )
                        except Exception as exc:
                            self.fail(
                                f"downstream AST error should fail closed, not raise: {exc}"
                            )

                    self.assertEqual(summary["ast_failure_count"], 1)
                    self.assertEqual(ast_path.read_bytes(), formal_ast)
                    failure = json.loads(
                        (output_dir / "parse_failures.jsonl").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertIn("forced downstream failure", failure["parser_stderr"])

    def test_fixed_loader_rejects_duplicate_sha(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            self._rewrite_selection(selection_manifest, [selection_row, selection_row])

            with self.assertRaisesRegex(ValueError, "duplicate source_sha256"):
                _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_rejects_invalid_stratum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            for invalid_stratum in ("unknown", ["linear_export"]):
                with self.subTest(invalid_stratum=invalid_stratum):
                    selection_row["calibration_stratum"] = invalid_stratum
                    self._rewrite_selection(selection_manifest, [selection_row])
                    with self.assertRaisesRegex(ValueError, "calibration_stratum"):
                        _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            (source_root / selection_row["source_path"]).unlink()

            with self.assertRaisesRegex(ValueError, "source path does not exist"):
                _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_rejects_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            selection_row["source_sha256"] = "a" * 64
            self._rewrite_selection(selection_manifest, [selection_row])

            with self.assertRaisesRegex(ValueError, "source_sha256 mismatch"):
                _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_rejects_size_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            selection_row["size_bytes"] += 1
            self._rewrite_selection(selection_manifest, [selection_row])

            with self.assertRaisesRegex(ValueError, "size_bytes mismatch"):
                _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_rejects_non_object_invalid_hash_and_unsafe_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            cases = [
                (["not-an-object"], "must contain an object"),
                (
                    [{**selection_row, "source_sha256": "A" * 64}],
                    "lowercase 64-character",
                ),
                (
                    [{**selection_row, "source_path": "../outside.js"}],
                    "confined under source_root",
                ),
            ]
            for rows, expected in cases:
                with self.subTest(expected=expected):
                    self._rewrite_selection(selection_manifest, rows)
                    with self.assertRaisesRegex(ValueError, expected):
                        _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_requires_literal_true_facts_and_integer_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            cases = [
                (
                    {**selection_row, "facts_supported": 1},
                    "facts_supported must be true",
                ),
                (
                    {**selection_row, "size_bytes": True},
                    "size_bytes must be an integer",
                ),
            ]
            for invalid_row, expected in cases:
                with self.subTest(expected=expected):
                    self._rewrite_selection(selection_manifest, [invalid_row])
                    with self.assertRaisesRegex(ValueError, expected):
                        _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_requires_exact_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            for missing_field in selection_row:
                with self.subTest(missing_field=missing_field):
                    incomplete = dict(selection_row)
                    incomplete.pop(missing_field)
                    self._rewrite_selection(selection_manifest, [incomplete])
                    with self.assertRaisesRegex(
                        ValueError, "schema mismatch.*missing fields"
                    ):
                        _load_fixed_selection_records(selection_manifest, source_root)

            self._rewrite_selection(
                selection_manifest, [{**selection_row, "unknown": "value"}]
            )
            with self.assertRaisesRegex(ValueError, "schema mismatch.*unknown fields"):
                _load_fixed_selection_records(selection_manifest, source_root)

    def test_fixed_loader_requires_nonempty_string_record_key_and_source_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, selection_row = self._fixture(root)
            cases = [
                ({**selection_row, "record_key": ""}, "record_key"),
                ({**selection_row, "record_key": 10}, "record_key"),
                ({**selection_row, "source_path": ""}, "source_path"),
                ({**selection_row, "source_path": 10}, "source_path"),
            ]
            for invalid_row, expected in cases:
                with self.subTest(expected=expected, value=invalid_row[expected]):
                    self._rewrite_selection(selection_manifest, [invalid_row])
                    with self.assertRaisesRegex(ValueError, expected):
                        _load_fixed_selection_records(selection_manifest, source_root)

    def test_build_requires_complete_authority_pair_without_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, _, _ = self._fixture(root)
            common = {
                "source_root": source_root,
                "parser_path": Path("scripts/parse_gee_js_with_locations.js"),
                "output_dir": root / "output",
            }
            with self.assertRaisesRegex(
                ValueError, "canonical_manifest and join_ledger"
            ):
                build_calibration(
                    canonical_manifest=None, join_ledger=root / "join.jsonl", **common
                )

    def test_cli_rejects_incomplete_manifest_mode_before_build(self):
        with self.assertRaises(SystemExit) as caught:
            main(
                [
                    "--canonical-manifest",
                    "canonical.jsonl",
                    "--source-root",
                    "sources",
                    "--parser",
                    "parser.js",
                    "--output-dir",
                    "output",
                ]
            )

        self.assertEqual(caught.exception.code, 2)

    def test_cli_selection_mode_ignores_missing_authority_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root, selection_manifest, _ = self._fixture(root)
            output_dir = root / "output"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                try:
                    result = main(
                        [
                            "--selection-manifest",
                            str(selection_manifest),
                            "--canonical-manifest",
                            str(root / "missing-canonical.jsonl"),
                            "--join-ledger",
                            str(root / "missing-join.jsonl"),
                            "--source-root",
                            str(source_root),
                            "--parser",
                            "scripts/parse_gee_js_with_locations.js",
                            "--output-dir",
                            str(output_dir),
                        ]
                    )
                except SystemExit as exc:
                    self.fail(
                        f"CLI rejected fixed selection mode with authority paths: {exc}"
                    )

            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue())["selected_source_count"], 1)
            ledger_inputs = json.loads(
                (output_dir / "hash_ledger.json").read_text(encoding="utf-8")
            )["inputs"]
            self.assertEqual(set(ledger_inputs), {"selection_manifest", "parser"})


if __name__ == "__main__":
    unittest.main()
