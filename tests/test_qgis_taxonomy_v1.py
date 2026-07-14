import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_taxonomy_v1 import (
    ADDITIONS,
    _load_legacy_hierarchy,
    build_taxonomy,
    main,
    validate_taxonomy,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_MAPPINGS = Path(
    os.environ.get("QGIS_TAXONOMY_BASE_MAPPINGS", ROOT / "outputs_v2" / "id_mappings_v2.json")
)
LEGACY_HIERARCHY = Path(
    os.environ.get("QGIS_TAXONOMY_LEGACY_HIERARCHY", ROOT / "classification_hierarchy.csv")
)


class QgisTaxonomyV1Tests(unittest.TestCase):
    def test_build_preserves_94_ids_and_adds_20_collision_free_classes(self):
        base = {f"L3_BASE_{index:03d}": index for index in range(94)}
        taxonomy, migration = build_taxonomy(base)

        self.assertEqual(len(taxonomy["code_to_token_id"]), 114)
        self.assertEqual(set(taxonomy["code_to_token_id"].values()), set(range(114)))
        self.assertEqual(
            {code: taxonomy["code_to_token_id"][code] for code in base},
            base,
        )
        self.assertEqual(taxonomy["code_to_token_id"]["L3_01_10_01"], 101)
        self.assertEqual(taxonomy["code_to_token_id"]["L3_02_05_14"], 107)
        self.assertEqual(migration["old_token_id_to_new_token_id"]["94"], 101)
        self.assertEqual(
            migration["semantic_migrations"]["L3_02_07_02"]["new_code"],
            "L3_02_07_03",
        )
        grid = next(row for row in taxonomy["added_classes"] if row["code"] == "L3_02_03_06")
        self.assertEqual(grid["l2_code"], "L2_02_03")
        self.assertEqual(validate_taxonomy(taxonomy, base), [])

    def test_serialized_artifacts_do_not_depend_on_runtime_profile(self):
        base = {f"L3_BASE_{index:03d}": index for index in range(94)}
        taxonomy, migration = build_taxonomy(base)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "taxonomy.json"
            path.write_text(json.dumps(taxonomy), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["profile"], "qgis_l3_v1_114_experimental")
        self.assertFalse(loaded["production_default"])
        self.assertEqual(migration["source_profile"], "v3_107_experimental")
        self.assertEqual(migration["source_profile_status"], "invalid_code_reuse")

    def test_real_registry_is_complete_and_collision_free(self):
        mappings = json.loads(BASE_MAPPINGS.read_text(encoding="utf-8"))
        legacy = _load_legacy_hierarchy(LEGACY_HIERARCHY)
        taxonomy, migration = build_taxonomy(mappings["l3"], legacy)

        self.assertEqual(len(legacy), 350)
        self.assertEqual(validate_taxonomy(taxonomy, mappings["l3"], legacy, migration), [])
        self.assertEqual(len(taxonomy["alias_to_code"]), sum(len(row["aliases"]) for row in ADDITIONS))
        for row in taxonomy["added_classes"]:
            self.assertTrue(row["name"])
            self.assertTrue(row["definition"])
            self.assertRegex(row["l2_code"], r"^L2_")
            self.assertRegex(row["l1_code"], r"^L1_")
            self.assertTrue(row["l2_name"])
            self.assertTrue(row["l1_name"])
        self.assertEqual(
            taxonomy["parent_metadata_overrides"]["L1_06"]["name"],
            "3D and TIN Analysis",
        )

    def test_new_code_collision_with_legacy_registry_fails(self):
        base = {f"L3_BASE_{index:03d}": index for index in range(94)}
        colliding_legacy = {
            "L3_01_03_05": {
                "name": "Conflicting Legacy Meaning",
                "definition": "Collision fixture",
                "l2_code": "L2_01_03",
                "l2_name": "Data Integration",
                "l1_code": "L1_01",
                "l1_name": "Data Management",
            }
        }
        with self.assertRaisesRegex(ValueError, "collides with legacy registry"):
            build_taxonomy(base, colliding_legacy)

    def test_validation_rejects_alias_and_migration_mismatch(self):
        base = {f"L3_BASE_{index:03d}": index for index in range(94)}
        taxonomy, migration = build_taxonomy(base)
        taxonomy["added_classes"][1]["aliases"].append(taxonomy["added_classes"][0]["aliases"][0].upper())
        migration["old_token_id_to_new_token_id"]["94"] = 94

        errors = validate_taxonomy(taxonomy, base, migration=migration)

        self.assertTrue(any(error.startswith("alias_collision:") for error in errors))
        self.assertTrue(any(error.startswith("migration_target_mismatch:94") for error in errors))

    def test_cli_records_reproducible_input_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            exit_code = main(
                [
                    "--base-id-mappings",
                    str(BASE_MAPPINGS),
                    "--legacy-hierarchy",
                    str(LEGACY_HIERARCHY),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            taxonomy = json.loads((output_dir / "qgis_l3_v1_114.json").read_text(encoding="utf-8"))
            taxonomy_bytes = (output_dir / "qgis_l3_v1_114.json").read_bytes()
            migration = json.loads(
                (output_dir / "qgis_l3_v1_114_migration_from_invalid_107.json").read_text(encoding="utf-8")
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(taxonomy["build_inputs"], migration["build_inputs"])
        self.assertNotIn(b"\r\n", taxonomy_bytes)
        self.assertTrue(taxonomy_bytes.endswith(b"\n"))
        self.assertRegex(taxonomy["build_inputs"]["base_id_mappings_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(taxonomy["build_inputs"]["legacy_hierarchy_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
