from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "census_qgis_mappy_match_algo_contract.py"
)
SPEC = importlib.util.spec_from_file_location("mappy_contract_census", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_contract_calls_requires_header_import_and_literal_argument() -> None:
    source = '''
# Plugin: mappy
# Version: v0.3.2
from ..mappy_utils import matchAlgo

def execute(layer):
    return processing.run(matchAlgo("native:buffer"), {"INPUT": layer})
'''

    assert MODULE.contract_calls(source) == [
        {
            "call_line": 7,
            "call_line_end": 7,
            "input_operator_id": "native:buffer",
        }
    ]


def test_contract_calls_rejects_local_rebinding_and_missing_version_header() -> None:
    rebound = '''
# Plugin: mappy
# Version: v0.3.2
from ..mappy_utils import matchAlgo
matchAlgo = lambda value: value
processing.run(matchAlgo("native:buffer"), {})
'''
    no_header = '''
from ..mappy_utils import matchAlgo
processing.run(matchAlgo("native:buffer"), {})
'''

    assert MODULE.contract_calls(rebound) == []
    assert MODULE.contract_calls(no_header) == []
