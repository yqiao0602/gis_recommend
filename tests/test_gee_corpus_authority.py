import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from src.gis_recommend.data.gee_corpus_authority import DEFAULT_BATCHES, build_authority, discover_source_instances, write_manifest_atomic

FIELDS = ["File Name", "Task Type", "Task Name", "DataSource", "Geospatial Values", "Time Ranges", "Task Description"]


class GeeCorpusAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.source = self.root / "source"; self.facts = self.root / "facts"; self.out = self.root / "out"
        self.source.mkdir(); self.facts.mkdir()

    def tearDown(self): self.tmp.cleanup()

    def source_file(self, batch, filename, text):
        folder = self.source / batch; folder.mkdir(parents=True, exist_ok=True)
        p = folder / filename; p.write_text(text, encoding="utf-8"); return p

    def facts_file(self, name, rows):
        p = self.facts / name
        with p.open("w", newline="", encoding="utf-8") as h:
            writer = csv.DictWriter(h, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
        return p

    def fact(self, filename, name="n", desc="d"):
        return {"File Name": filename, "Task Type": "x", "Task Name": name, "DataSource": "s", "Geospatial Values": "g", "Time Ranges": "t", "Task Description": desc}

    def test_real_source_discovery_and_exclusions(self):
        self.source_file("data10000", "script_881.txt", "same")
        self.source_file("data10000", "script_12074 .txt", "invalid")
        self.source_file("data10000_AST_failed", "script_881.txt", "bad")
        self.source_file("qgis", "script_881.txt", "bad")
        self.source_file("data0", "script_1.txt", "bad")
        rows = discover_source_instances(self.source, batches=("data10000",))
        self.assertEqual([r["script_filename"] for r in rows], ["script_12074 .txt", "script_881.txt"])
        invalid = next(r for r in rows if r["script_filename"].startswith("script_12074"))
        self.assertEqual(invalid["filename_status"], "invalid_source_filename")
        self.assertEqual(invalid["script_id"], "12074")

    def test_duplicate_content_mirror_and_canonical_instances(self):
        self.source_file("data280000", "script_881.txt", "same")
        self.source_file("data290000", "script_992.txt", "same")
        result = build_authority(self.source, self.facts, batches=("data280000", "data290000"))
        rows = result["source_instances"]
        mirror = next(r for r in rows if r["batch_name"] == "data290000")
        self.assertEqual(mirror["filename_status"], "valid_source_filename")
        self.assertEqual(mirror["instance_status"], "known_mirror_instance")
        canonical = next(r for r in result["canonical_sources"] if r["source_sha256"] == mirror["source_sha256"])
        self.assertEqual(len(canonical["instances"]), 2)
        self.assertIn("data290000/script_992.txt", [r["source_path"] for r in canonical["instances"]])

    def test_data290000_duplicate_without_data280000_is_not_known_mirror(self):
        self.source_file("data290000", "script_881.txt", "same")
        self.source_file("data300000", "script_992.txt", "same")
        result = build_authority(
            self.source,
            self.facts,
            batches=("data290000", "data300000"),
        )
        row = next(
            item
            for item in result["source_instances"]
            if item["batch_name"] == "data290000"
        )
        self.assertEqual(row["instance_status"], "source_duplicate_content")

    def test_exact_join_conflict_mismatch_and_missing(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.source_file("data20000", "script_881.txt", "b")
        self.source_file("data30000", "script_992.txt", "c")
        self.facts_file("facts_summary10000.csv", [self.fact("script_881.txt")])
        self.facts_file("facts_summary20000.csv", [self.fact("script_881.txt", "one"), self.fact("script_881.txt", "two"), self.fact("script_992.txt")])
        self.facts_file("facts_summary30000.csv", [self.fact("script_404.txt")])
        result = build_authority(self.source, self.facts, batches=("data10000", "data20000", "data30000"))
        statuses = [r["join_status"] for r in result["join_ledger"]]
        self.assertIn("authoritative_exact_batch_join", statuses)
        self.assertEqual(statuses.count("facts_conflict"), 2)
        self.assertIn("batch_range_mismatch", statuses)
        self.assertIn("facts_source_missing", statuses)
        self.assertIn("source_facts_missing", statuses)

    def test_hyphen_facts_maps_to_data280000(self):
        self.source_file("data280000", "script_881.txt", "a")
        self.facts_file("facts_summary280000-290000.csv", [self.fact("script_881.txt")])
        result = build_authority(self.source, self.facts, batches=("data280000",))
        row = next(r for r in result["join_ledger"] if r["facts_file"])
        self.assertEqual(row["join_status"], "authoritative_exact_batch_join")

    def test_legacy_290000_facts_maps_to_data280000(self):
        self.source_file("data280000", "script_881.txt", "a")
        self.facts_file("facts_summary290000.csv", [self.fact("script_881.txt")])
        row = next(r for r in build_authority(self.source, self.facts, batches=("data280000",))["join_ledger"] if r["facts_file"])
        self.assertEqual(row["join_status"], "authoritative_exact_batch_join")

    def test_file_name_cross_batch_only_diagnostic(self):
        self.source_file("data10000", "script_881.txt", "a")
        (self.source / "data20000").mkdir()
        self.facts_file("facts_summary20000.csv", [self.fact("script_881.txt")])
        result = build_authority(self.source, self.facts, batches=("data10000", "data20000"))
        row = next(r for r in result["join_ledger"] if r["facts_file"])
        self.assertEqual(row["join_status"], "batch_range_mismatch"); self.assertFalse(row["authoritative"])

    def test_stable_outputs_cli_and_output_guards(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.facts_file("facts_summary10000.csv", [self.fact("script_881.txt")])
        result = build_authority(self.source, self.facts, batches=("data10000",)); write_manifest_atomic(result, self.out)
        first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.out.iterdir()}
        (self.out / "stale.txt").write_text("stale", encoding="utf-8")
        write_manifest_atomic(result, self.out); second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.out.iterdir()}
        self.assertNotIn("stale.txt", second)
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"source_instances.jsonl", "canonical_sources.jsonl", "facts_ledger.jsonl", "join_ledger.jsonl", "summary.json", "report.md", "hash_ledger.json"})
        script = Path("scripts/build_gee_corpus_authority_manifest.py"); cli_out = self.root / "cli-out"
        subprocess.run([sys.executable, str(script), "--source-root", str(self.source), "--facts-root", str(self.facts), "--output-dir", str(cli_out), "--batch", "data10000"], check=True)
        self.assertTrue((cli_out / "summary.json").exists())
        for bad in (self.source / "out", self.facts / "out"):
            with self.assertRaises(subprocess.CalledProcessError): subprocess.run([sys.executable, str(script), "--source-root", str(self.source), "--facts-root", str(self.facts), "--output-dir", str(bad), "--batch", "data10000"], check=True)

    def test_default_batches_are_explicit_and_missing_batch_fails(self):
        self.assertEqual(len(DEFAULT_BATCHES), 31); self.assertNotIn("data0", DEFAULT_BATCHES)
        with self.assertRaises(ValueError): build_authority(self.source, self.facts, batches=("data10000",))

    def test_join_uses_batch_and_filename_indexes(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.facts_file("facts_summary10000.csv", [self.fact("script_881.txt")])
        source = Path("src/gis_recommend/data/gee_corpus_authority.py").read_text(encoding="utf-8")
        self.assertIn("by_batch_name", source)
        self.assertIn("by_name", source)
        result = build_authority(self.source, self.facts, batches=("data10000",))
        self.assertEqual(result["summary"]["counts"]["source_instances"], 1)

    def test_report_contains_actual_counts_and_hash_ledger_inputs(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.facts_file("facts_summary10000.csv", [self.fact("script_881.txt")])
        result = build_authority(self.source, self.facts, batches=("data10000",)); write_manifest_atomic(result, self.out)
        report = (self.out / "report.md").read_text(encoding="utf-8")
        ledger = json.loads((self.out / "hash_ledger.json").read_text(encoding="utf-8"))
        self.assertIn("source_instances: 1", report)
        self.assertIn("source_ledger_content_sha256", ledger["artifacts"])
        self.assertIn("facts_ledger_content_sha256", ledger["artifacts"])

    def test_summary_exposes_duplicate_join_and_per_batch_counts(self):
        self.source_file("data280000", "script_881.txt", "same")
        self.source_file("data290000", "script_881.txt", "same")
        self.facts_file(
            "facts_summary280000-290000.csv",
            [self.fact("script_881.txt")],
        )
        result = build_authority(
            self.source,
            self.facts,
            batches=("data280000", "data290000"),
        )
        counts = result["summary"]["counts"]
        self.assertEqual(counts["duplicate_groups"], 1)
        self.assertEqual(counts["duplicate_extra_instances"], 1)
        self.assertEqual(counts["unique_source_contents"], 1)
        self.assertEqual(counts["exact_facts_joins"], 1)
        per_batch = result["summary"]["per_batch"]
        self.assertEqual(per_batch["data280000"]["source_instances"], 1)
        self.assertEqual(per_batch["data280000"]["valid_source_filenames"], 1)
        self.assertEqual(per_batch["data280000"]["canonical_sources"], 1)
        self.assertEqual(per_batch["data280000"]["duplicate_groups"], 1)
        self.assertEqual(per_batch["data280000"]["exact_facts_joins"], 1)
        self.assertEqual(per_batch["data290000"]["known_mirror_instances"], 1)
        self.assertEqual(
            result["summary"]["facts_coverage_unit"],
            "source_content_sha256_with_exact_instance_join",
        )

    def test_unknown_facts_range_fails_and_subset_ignores_other_known_batches(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.facts_file("facts_summary10000.csv", [self.fact("script_881.txt")])
        self.facts_file("facts_summary20000.csv", [self.fact("script_992.txt")])
        result = build_authority(self.source, self.facts, batches=("data10000",))
        self.assertEqual(result["summary"]["counts"]["facts_rows"], 1)

        self.facts_file(
            "facts_summary270000-280000.csv",
            [self.fact("script_881.txt")],
        )
        with self.assertRaises(ValueError):
            build_authority(self.source, self.facts, batches=("data10000",))

    def test_nested_source_path_fails_and_record_key_is_explicit(self):
        self.source_file("data10000", "script_881.txt", "a")
        rows = discover_source_instances(self.source, batches=("data10000",))
        self.assertEqual(rows[0]["record_key"], "data10000/script_881.txt")

        self.source_file("data10000/nested", "script_992.txt", "b")
        with self.assertRaises(ValueError):
            discover_source_instances(self.source, batches=("data10000",))

    def test_batch_order_is_normalized(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.source_file("data20000", "script_992.txt", "b")
        forward = build_authority(
            self.source,
            self.facts,
            batches=("data10000", "data20000"),
        )
        reverse = build_authority(
            self.source,
            self.facts,
            batches=("data20000", "data10000"),
        )
        self.assertEqual(forward["summary"], reverse["summary"])

    def test_failed_publish_and_failed_restore_preserve_backup(self):
        self.source_file("data10000", "script_881.txt", "a")
        self.facts_file("facts_summary10000.csv", [self.fact("script_881.txt")])
        result = build_authority(self.source, self.facts, batches=("data10000",))
        write_manifest_atomic(result, self.out)
        real_replace = __import__("os").replace
        calls = 0

        def failing_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_replace(source, destination)
            raise OSError(f"injected replace failure {calls}")

        with mock.patch(
            "src.gis_recommend.data.gee_corpus_authority.os.replace",
            side_effect=failing_replace,
        ):
            with self.assertRaisesRegex(RuntimeError, "backup preserved"):
                write_manifest_atomic(result, self.out)

        backups = list(self.root.glob(f".{self.out.name}.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "summary.json").is_file())


if __name__ == "__main__": unittest.main()
