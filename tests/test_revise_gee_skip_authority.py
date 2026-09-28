import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.revise_gee_skip_authority import revise_skip_authority


class ReviseGeeSkipAuthorityTests(unittest.TestCase):
    def test_removes_exact_operator_and_binds_parent_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "skip_v1.json"
            output = root / "skip_v2.json"
            source.write_text(
                json.dumps(
                    {
                        "version": "v1",
                        "skip_operators": [
                            "ee.image.get",
                            "ee.imagecollection.sort",
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = revise_skip_authority(
                input_path=source,
                output_path=output,
                version="v2-sort-is-output-relevant",
                remove_operators=["ee.imagecollection.sort"],
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["version"], "v2-sort-is-output-relevant")
            self.assertEqual(payload["skip_operators"], ["ee.image.get"])
            self.assertEqual(
                payload["parent_authority"]["sha256"],
                hashlib.sha256(source.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                payload["changes"]["removed_operators"],
                ["ee.imagecollection.sort"],
            )
            self.assertEqual(result["skip_operator_count"], 1)

    def test_missing_removal_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "skip_v1.json"
            source.write_text(
                json.dumps({"version": "v1", "skip_operators": ["ee.image.get"]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "not present"):
                revise_skip_authority(
                    input_path=source,
                    output_path=root / "skip_v2.json",
                    version="v2",
                    remove_operators=["ee.imagecollection.sort"],
                )


if __name__ == "__main__":
    unittest.main()
