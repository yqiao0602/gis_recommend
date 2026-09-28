from __future__ import annotations

import unittest

from scripts.filter_qgis_api_boundary_candidates import filter_candidates


def _terminal(line: int, payload: str) -> dict:
    return {
        "call_name": "writer.addFeature",
        "terminal_evidence": True,
        "line_start": line,
        "line_end": line,
        "receiver": "writer",
        "consumed_names": [payload, "writer"],
        "produced_names": [],
        "control_path": [],
    }


def _source_row(adjacent_payload: str) -> dict:
    mutation = {
        "call_name": "output.setGeometry",
        "terminal_evidence": False,
        "line_start": 8,
        "line_end": 8,
        "receiver": "output",
        "consumed_names": ["geometry", "output"],
        "produced_names": ["output"],
        "control_path": [],
    }
    candidate_terminal = _terminal(10, "output")
    return {
        "record_id": "record",
        "source_authority_key": "body:sha",
        "candidate_units": [
            {
                "candidate_id": "candidate",
                "lexical_scope": "export",
                "steps": [mutation, candidate_terminal],
            }
        ],
        "deferred_units": [
            {
                "lexical_scope": "export",
                "steps": [_terminal(11, adjacent_payload)],
            }
        ],
    }


class FilterQgisApiBoundaryCandidatesTest(unittest.TestCase):
    def test_excludes_adjacent_same_writer_with_different_payload(self) -> None:
        eligible, excluded = filter_candidates([_source_row("original")])

        self.assertEqual(eligible, [])
        self.assertEqual(len(excluded), 1)
        self.assertEqual(
            excluded[0]["reason"],
            "adjacent_same_receiver_different_payload_terminal",
        )

    def test_keeps_adjacent_retry_of_same_payload(self) -> None:
        eligible, excluded = filter_candidates([_source_row("output")])

        self.assertEqual([row["candidate_id"] for row in eligible], ["candidate"])
        self.assertEqual(excluded, [])


if __name__ == "__main__":
    unittest.main()
