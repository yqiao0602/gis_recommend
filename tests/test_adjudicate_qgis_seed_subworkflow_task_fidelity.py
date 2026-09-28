from scripts.adjudicate_qgis_seed_subworkflow_task_fidelity import REVIEWS, _dependency_edges


def test_frozen_task_fidelity_review_distribution() -> None:
    decisions = [row["decision"] for row in REVIEWS.values()]
    assert decisions.count("gold") == 5
    assert decisions.count("retain_silver") == 4
    assert decisions.count("reject") == 2


def test_projected_edges_keep_only_source_backed_dependencies() -> None:
    parent = {"dependency_edges": [[0, 1], [0, 2], [0, 3], [2, 3]]}
    assert _dependency_edges(parent, [0, 3]) == [[0, 1]]
    assert _dependency_edges(parent, [0, 2, 3]) == [[0, 1], [0, 2], [1, 2]]
