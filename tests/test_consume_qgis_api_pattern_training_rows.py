from scripts.consume_qgis_api_pattern_training_rows import consume


def _ctx(record_id: str, *, doc=None, comments=None, classes=None, functions=None, chain=None, l3=None, sha=None) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": sha or record_id + "0" * 58,
        "chain": chain or ["buffer", "simplify"],
        "l3_sequence": l3 or ["L3_02_01_01", "L3_02_05_01"],
        "chain_signature": "|".join(chain or ["buffer", "simplify"]),
        "function_docstring": doc,
        "module_docstring": None,
        "nearby_comments": comments or [],
        "classes": classes,
        "functions": functions,
    }


def _existing(sha: str | None = None, l3: list | None = None, text: str | None = None) -> dict:
    return {"source_sha256": sha or "x" * 64, "l3_codes": ["<START>"] + (l3 or []) + ["<END>"], "task_description": text or ""}


def test_docstring_text_survives(tmp_path=None) -> None:
    ledger, summary = consume(
        [_ctx("a", doc="Buffer the roads then simplify the result.")],
        [_existing()],
    )
    kept = [row for row in ledger if row["stage"] is None]
    assert len(kept) == 1
    assert kept[0]["task_text"] == "Buffer the roads then simplify the result."
    assert kept[0]["task_text_source"] == "docstring"


def test_comment_and_domain_scope_text_sources() -> None:
    rows = [
        _ctx("a", comments=["# buffer roads for noise analysis"]),
        _ctx("b", classes=["RoadNoiseTool"], functions=["process_buffer"], l3=["L3_02_01_01", "L3_02_03_05"]),
        _ctx("c", classes=["Helper"], functions=["run"], l3=["L3_01_05_02", "L3_02_02_01"]),
    ]
    ledger, _ = consume(rows, [_existing()])
    stages = {row["record_id"]: row["stage"] for row in ledger}
    kinds = {row["record_id"]: row.get("task_text_source") for row in ledger}
    assert stages["a"] is None and kinds["a"] == "task_comment"
    assert stages["b"] is None and kinds["b"] == "domain_named_scope"
    assert stages["c"] == "task_text_reject"


def test_no_context_rejects_with_reason() -> None:
    ledger, summary = consume([_ctx("a", doc="", comments=[], classes=None, functions=None)], [_existing()])
    assert ledger[0]["stage"] == "task_text_reject"
    assert ledger[0]["reason"] == "no_source_context"
    assert summary["funnel"]["no_source_context"] == 1


def test_internal_l3_sequence_dedup() -> None:
    first = _ctx("a", doc="first sample task text")
    second = _ctx("b", doc="second sample task text")
    ledger, summary = consume([first, second], [_existing(l3=["L3_03_03_A"], text="unrelated")])
    kept = [row for row in ledger if row["stage"] is None]
    deduped = [row for row in ledger if row["stage"] == "dedup_internal"]
    assert len(kept) == 1 and len(deduped) == 1
    assert summary["funnel"]["dedup_internal_l3_sequence"] == 1


def test_508_pool_hits_by_sha_l3_and_text() -> None:
    sha = "f" * 64
    rows = [
        _ctx("a", sha=sha, doc="text"),
        _ctx("b", doc="text", l3=["L3_01_10_01", "L3_02_01_01"]),
        _ctx("c", doc="identical existing text", l3=["L3_02_02_01", "L3_02_03_05"]),
    ]
    existing = [
        _existing(sha=sha),
        _existing(l3=["L3_01_10_01", "L3_02_01_01"]),
        _existing(text="identical existing text"),
    ]
    ledger, summary = consume(rows, existing)
    stages = {row["record_id"]: row["stage"] for row in ledger}
    assert stages["a"] == "dedup_508" and stages["b"] == "dedup_508" and stages["c"] == "dedup_508"
    assert summary["funnel"]["hit_508_source_sha"] == 1
    assert summary["funnel"]["hit_508_l3_sequence"] == 1


def test_gates_stay_closed() -> None:
    ledger, summary = consume([_ctx("a", doc="a real task description")], [_existing(l3=["L3_03_03_A"], text="unrelated")])
    kept = [row for row in ledger if row["stage"] is None]
    assert kept[0]["training_admission"] == "candidate_pending_tokenizer_and_v4_gates"
    assert summary["training_rows_emitted"] == 0
    assert summary["formal_authority_modified"] is False
