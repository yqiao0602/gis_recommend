from scripts.qualify_qgis_processing_operator_semantics import qualify

MAPPING = {
    "native:buffer": "L3_02_01_01",
    "native:dissolve": "L3_02_03_05",
    "gdal:hillshade": "L3_04_01_03",
}
TAXONOMY = {
    "L3_02_01_01": {"l3_code": "L3_02_01_01", "token_id": 6, "l3_name": "Buffer"},
    "L3_02_03_05": {"l3_code": "L3_02_03_05", "token_id": 15, "l3_name": "Collect Features"},
    "L3_04_01_03": {"l3_code": "L3_04_01_03", "token_id": 22, "l3_name": "Hillshade"},
}


def _call(operator: str, provider: str | None = None, resolution: str = "literal_source_evidence") -> dict:
    return {
        "operator_id": operator,
        "entrypoint": "run",
        "resolution_kind": resolution,
        "parameter_evidence": {"status": "verified_static_dict", "completeness": "static_parameter_partial"},
        "io_evidence": {"status": "parameter_keys_present"},
        "provider_evidence": {"status": "operator_id_prefix", "provider_id": provider},
    }


def _row(operator: str, record_id: str, status: str = "source_verified_ast") -> dict:
    provider = operator.partition(":")[0] if ":" in operator else None
    return {
        "record_id": record_id,
        "status": status,
        "source_sha256": record_id + "0" * 52,
        "schema": "gis_recommend.qgis_processing_operator_evidence_sidecar.v1",
        "calls": [_call(operator, provider)],
    }


def _ledger(rows, alias_proofs=None):
    ledger, summary = qualify(rows, MAPPING, TAXONOMY, alias_proofs or {})
    return {entry["operator_id"]: entry for entry in ledger}, summary


def test_exact_mapping_operator_qualifies() -> None:
    ledger, summary = _ledger([_row("native:dissolve", "a"), _row("native:dissolve", "b")])
    entry = ledger["native:dissolve"]
    assert entry["qualification_status"] == "QUALIFIED"
    assert entry["qualification_path"] == "exact_mapping"
    assert entry["l3"]["proposed_l3_code"] == "L3_02_03_05"
    assert entry["l3"]["token_id"] == 15
    assert entry["l3"]["ambiguity"] == "unambiguous_single_authority_mapping"
    assert entry["training_rows_emitted"] == 0
    assert summary["qualification_status_counts"]["QUALIFIED"] == 1


def test_qgis_alias_qualifies_only_with_proof_for_every_row() -> None:
    rows = [_row("qgis:buffer", "a"), _row("qgis:buffer", "b")]
    proofs = {("a", "qgis:buffer"): {"status": "verified_exact_same_slug"}}
    ledger, _ = _ledger(rows, proofs)
    assert ledger["qgis:buffer"]["qualification_status"] == "DEFERRED"
    assert ledger["qgis:buffer"]["qualification_path"] == "alias_proof_incomplete"
    assert ledger["qgis:buffer"]["alias"]["verified_rows"] == 1

    proofs["b", "qgis:buffer"] = {"status": "verified_exact_same_slug"}
    ledger, _ = _ledger(rows, proofs)
    entry = ledger["qgis:buffer"]
    assert entry["qualification_status"] == "QUALIFIED"
    assert entry["qualification_path"] == "verified_alias_same_slug"
    assert entry["l3"]["proposed_l3_code"] == "L3_02_01_01"
    assert "via native:buffer" in entry["l3"]["mapping_source"]


def test_gdalogr_alias_stays_deferred_without_precedent() -> None:
    ledger, _ = _ledger([_row("gdalogr:hillshade", "a")])
    entry = ledger["gdalogr:hillshade"]
    assert entry["qualification_status"] == "DEFERRED"
    assert entry["qualification_path"] == "alias_deferred_no_precedent"
    assert entry["alias"]["canonical_operator"] == "gdal:hillshade"
    assert entry["defer_reason"] == "no_precedent_authority_for_provider_alias"


def test_catalog_provider_without_mapping_is_deferred_not_failed() -> None:
    ledger, _ = _ledger([_row("native:rastercalc", "a")])
    entry = ledger["native:rastercalc"]
    assert entry["qualification_status"] == "DEFERRED"
    assert entry["qualification_path"] == "no_mapping_authority"
    assert entry["defer_reason"] == "no_mapping_in_composed_stable124"


def test_third_party_provider_fails_closed() -> None:
    ledger, _ = _ledger([_row("umep:spatial_data: dsm generator", "a"), _row("model:etl_cobol", "b")])
    assert ledger["umep:spatial_data: dsm generator"]["qualification_status"] == "FAIL_CLOSED"
    assert ledger["model:etl_cobol"]["qualification_status"] == "FAIL_CLOSED"
    assert ledger["model:etl_cobol"]["fail_reason"] == "third_party_or_malformed_provider_outside_catalog"


def test_mapping_target_outside_taxonomy_is_deferred() -> None:
    ledger, _ = qualify([_row("native:dissolve", "a")], MAPPING, {"L3_99_99_99": {"token_id": 99, "l3_name": "Ghost"}}, {})
    assert ledger[0]["qualification_status"] == "DEFERRED"
    assert ledger[0]["qualification_path"] == "l3_target_outside_taxonomy"


def test_unverified_source_rows_block_qualification() -> None:
    ledger, _ = _ledger([_row("native:dissolve", "a", status="deferred")])
    entry = ledger["native:dissolve"]
    assert entry["qualification_status"] == "DEFERRED"
    assert entry["operator_identity"]["status"] == "deferred_source_evidence_incomplete"
    assert entry["defer_reason"] == "operator_identity_evidence_incomplete"


def test_evidence_coverage_is_recorded_without_gating() -> None:
    ledger, summary = _ledger([_row("native:dissolve", "a")])
    entry = ledger["native:dissolve"]
    assert entry["parameter_evidence"]["status_counts"] == {"verified_static_dict": 1}
    assert entry["parameter_evidence"]["completeness_counts"] == {"static_parameter_partial": 1}
    assert entry["io_evidence"]["status_counts"] == {"parameter_keys_present": 1}
    assert entry["training_admission"] == "not_granted_qualification_only"
    assert summary["training_rows_emitted"] == 0
