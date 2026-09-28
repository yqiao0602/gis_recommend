import json
import subprocess
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "scripts" / "parse_gee_js_with_locations.js"
TMP_ROOT = ROOT / ".tmp_test_parse_gee_js"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class ParseGeeJavaScriptWithLocationsTests(unittest.TestCase):
    def test_parser_requests_locations_and_ranges_from_acorn(self):
        root = _workspace_dir("locations")
        try:
            source = root / "script.js"
            output = root / "ast.json"
            source.write_text("var image = ee.Image(1);", encoding="utf-8")

            completed = subprocess.run(
                ["node", str(PARSER), str(source), str(output)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            ast = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(ast["type"], "Program")
            self.assertEqual(ast["body"][0]["type"], "VariableDeclaration")
            self.assertIn("loc", ast["body"][0])
            self.assertIn("range", ast["body"][0])
            self.assertEqual(ast["body"][0]["loc"]["start"]["line"], 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
