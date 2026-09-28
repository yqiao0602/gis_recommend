from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_qgis_llm_literal_holdout.py"
SPEC = importlib.util.spec_from_file_location("qgis_llm_literal_holdout", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_literal_catalog_ids_accepts_exact_and_verified_qgis_to_native_alias() -> None:
    source = '''
processing.run("native:buffer", {})
processing.run("qgis:joinattributesbylocation", {})
processing.run(dynamic_id, {})
'''

    assert MODULE._literal_catalog_ids(
        source, {"native:buffer", "native:joinattributesbylocation"}
    ) == {"native:buffer", "native:joinattributesbylocation"}


def test_remote_program_carries_only_opaque_catalog_and_exclusion_values() -> None:
    program = MODULE._remote_program()

    assert "sys.stdin.buffer.readline" in program
    assert "source_count" in program
