from scripts.audit_gee_full_source_semantics import (
    _line_span_is_valid,
    _source_method_names,
    _source_supports_output_class,
    _source_supports_temporal_claim,
)


def test_multiline_ast_span_allows_independent_end_column() -> None:
    assert _line_span_is_valid(
        ["var image = source", "  .filterDate(start, end)", "  .median();"],
        {"start_line": 1, "start_column": 12, "end_line": 3, "end_column": 12},
    )


def test_filter_date_equivalent_is_counted() -> None:
    names = _source_method_names("collection.filter(ee.Filter.date('2020-01-01', '2020-02-01'))")
    assert "filter" in names
    assert "filterdate" in names


def test_static_date_concatenation_is_supported_but_dynamic_is_not() -> None:
    source = "var year = '2020';\nvar start = year + '-01-01';\nvar end = year + '-05-31';"
    assert _source_supports_temporal_claim(source, "2020-01-01", "2020-05-31")
    assert not _source_supports_temporal_claim("var start = runtimeValue;", "2020-01-01", "2020-05-31")


def test_video_output_accepts_export_video_destination() -> None:
    assert _source_supports_output_class("Export.video.toDrive({collection: data});", "video")


def test_table_output_accepts_export_table_destination() -> None:
    assert _source_supports_output_class("Export.table.toDrive({collection: data});", "table")


def test_image_output_accepts_export_image_asset_destination() -> None:
    assert _source_supports_output_class("Export.image.toAsset({image: data});", "image")
