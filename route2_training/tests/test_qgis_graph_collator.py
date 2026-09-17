"""Graph round-trip tests — the core QGIS grounding signal (owner rule 4)."""

import unittest

from route2_training.harness import graph_to_text, text_to_graph


class TestGraphRoundTrip(unittest.TestCase):
    def test_linear_chain(self):
        processes = [
            {"process_id": "p0", "operator_id": "native:buffer"},
            {"process_id": "p1", "operator_id": "native:dissolve"},
        ]
        links = [{"source_process_id": "p0", "target_process_id": "p1"}]
        t = graph_to_text(processes, links)
        self.assertEqual(t, "P:p0:native:buffer P:p1:native:dissolve L:p0>p1")
        p2, l2 = text_to_graph(t)
        self.assertEqual(p2, processes)
        self.assertEqual(l2, links)

    def test_dag_branch_preserved(self):
        processes = [
            {"process_id": "p0", "operator_id": "native:clip"},
            {"process_id": "p1", "operator_id": "gdal:rastercalculator"},
            {"process_id": "p2", "operator_id": "native:fieldcalculator"},
        ]
        links = [  # branch: p0 -> p1 and p0 -> p2
            {"source_process_id": "p0", "target_process_id": "p1"},
            {"source_process_id": "p0", "target_process_id": "p2"},
        ]
        t = graph_to_text(processes, links)
        p2, l2 = text_to_graph(t)
        self.assertEqual(l2, links)          # branching survives exactly
        self.assertEqual(p2, processes)

    def test_multi_parent_merge(self):
        processes = [
            {"process_id": "p0", "operator_id": "a"},
            {"process_id": "p1", "operator_id": "b"},
            {"process_id": "p2", "operator_id": "c"},
        ]
        links = [
            {"source_process_id": "p0", "target_process_id": "p2"},
            {"source_process_id": "p1", "target_process_id": "p2"},
        ]
        p2, l2 = text_to_graph(graph_to_text(processes, links))
        self.assertEqual(l2, links)

    def test_operator_ids_with_colons_survive(self):
        # provider-qualified ids contain ':' — split(':' , 2) must keep them whole
        processes = [{"process_id": "p0", "operator_id": "gdal:rastercalculator"}]
        links = []
        t = graph_to_text(processes, links)
        self.assertEqual(t, "P:p0:gdal:rastercalculator")
        p2, l2 = text_to_graph(t)
        self.assertEqual(p2[0]["operator_id"], "gdal:rastercalculator")

    def test_empty_graph(self):
        self.assertEqual(graph_to_text([], []), "")
        self.assertEqual(text_to_graph(""), ([], []))

    def test_malformed_token_fails_closed(self):
        with self.assertRaises(ValueError):
            text_to_graph("P:p0:native:buffer X:junk")

    def test_link_without_processes_is_representable(self):
        # isolated links (shouldn't occur in v2a but round-trip must not lie)
        links = [{"source_process_id": "p5", "target_process_id": "p7"}]
        p2, l2 = text_to_graph(graph_to_text([], links))
        self.assertEqual(l2, links)

    def test_projected_and_patched_links_indistinguishable_by_structure(self):
        # link kind is metadata in v2a rows (link_kinds), NOT part of the
        # serialized structure — round-trip must not need it
        processes = [
            {"process_id": "p0", "operator_id": "native:clip"},
            {"process_id": "p1", "operator_id": "native:buffer"},
        ]
        links = [{"source_process_id": "p0", "target_process_id": "p1"}]
        p2, l2 = text_to_graph(graph_to_text(processes, links))
        self.assertEqual((p2, l2), (processes, links))


class TestPromptSuffixOrdering(unittest.TestCase):
    """Regression: suffix must come AFTER the task text (train/eval match)."""

    def test_prompt_precedes_suffix(self):
        class Tok:
            eos_token_id = 2; bos_token_id = None; pad_token_id = 0
            def encode(self, t, add_special_tokens=False):
                return [ord(c) % 250 + 3 for c in t]
        from route2_training.collators.qgis_graph_collator import QgisGraphCollator
        col = QgisGraphCollator(Tok(), max_len=512)
        e = col.encode_pair("TASKTEXT", "P:p0:op")
        parts = []
        for i in e["input_ids"]:
            parts.append("?" if not isinstance(i, int) or i < 3
                         else chr((i - 3) % 90 + 32))
        decoded = "".join(parts)
        task_pos = decoded.find("TASKTEXT")
        suffix_pos = decoded.find("workflow")
        self.assertGreater(suffix_pos, task_pos, "suffix must follow task text")


if __name__ == "__main__":
    unittest.main()
