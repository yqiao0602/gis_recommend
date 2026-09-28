import json

from gis_recommend.data.qgis_task_description import (
    audit_task_description,
    build_task_description,
    extract_literal_parameter_facts,
)


def _record(*, scope: str = "whole_processing_scope") -> dict:
    return {
        "record_id": "record-1",
        "operator_ids": ["native:buffer", "native:centroids"],
        "dependency_edges": [[0, 1]],
        "call_sites": [
            {
                "ordinal": 1,
                "operator_id": "native:buffer",
                "param_keys": ["INPUT", "DISTANCE", "OUTPUT"],
                "output_role": {"role": "assigned", "target": "buffered"},
            },
            {
                "ordinal": 2,
                "operator_id": "native:centroids",
                "param_keys": ["INPUT", "OUTPUT"],
                "output_role": {"role": "assigned", "target": "centroids"},
            },
        ],
        "workflow_unit_scope": scope,
        "mapped_l3_chain": ["L3_BUFFER", "L3_CENTROID"],
    }


def test_build_description_covers_all_steps_and_dependency() -> None:
    result = build_task_description(_record())

    assert result["description_fidelity_status"] == "candidate"
    assert "创建缓冲区" in result["task_description"]
    assert "提取质心" in result["task_description"]
    assert "缓冲区结果" in result["task_description"]
    assert result["known_omissions"] == []


def test_local_subworkflow_is_explicitly_scoped() -> None:
    result = build_task_description(_record(scope="local_subworkflow"))

    assert "局部工作流" in result["task_name"]
    assert "局部工作流" in result["task_description"]
    assert "完整任务" not in result["task_description"]


def test_description_does_not_copy_legacy_source_text() -> None:
    record = _record()
    record["task_text"] = "Source repo: unrelated/project export dialog"
    result = build_task_description(record)

    assert "repo" not in result["task_description"].lower()
    assert "source" not in result["task_description"].lower()
    assert "export" not in result["task_description"].lower()


def test_missing_operator_phrase_fails_closed() -> None:
    record = _record()
    record["operator_ids"] = ["native:buffer", "provider:unknown"]

    result = build_task_description(record)

    assert result["description_fidelity_status"] == "deferred"
    assert result["task_description"] == ""
    assert result["known_omissions"] == ["missing_operator_phrase:provider:unknown"]


def test_catalog_exact_operators_have_deterministic_semantics() -> None:
    expected_actions = {
        "gdal:cliprasterbymasklayer": "按矢量掩膜裁剪栅格",
        "native:zonalstatisticsfb": "按多边形分区计算栅格统计量",
        "native:clip": "使用多边形图层裁剪矢量要素",
        "native:reclassifybytable": "按分级表重分类栅格",
        "native:mergevectorlayers": "合并多个矢量图层",
        "native:addautoincrementalfield": "添加自增整数字段",
        "native:deletecolumn": "删除指定字段",
        "native:renametablefield": "重命名字段",
        "saga:splitrgbbands": "拆分栅格的红绿蓝波段",
        "gdal:extractprojection": "提取栅格投影并写入世界文件",
        "gdal:rasterize": "将矢量几何栅格化",
        "gdal:fillnodata": "插值填充栅格无数据区域",
        "native:zonalhistogram": "按多边形分区统计栅格值直方图",
        "gdal:rastercalculator": "执行栅格计算",
        "gdal:merge": "合并多个栅格文件",
        "native:rasterlayerstatistics": "计算指定栅格波段的全局统计量",
    }

    for operator_id, action in expected_actions.items():
        record = _record()
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert result["description_policy"] == "deterministic_operator_dag_zh_v5"
        assert action in result["task_description"], operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_stable106_core_operators_have_deterministic_semantics() -> None:
    expected_actions = {
        "native:creategrid": "创建规则矢量网格",
        "native:joinattributestable": "按指定字段连接属性表",
        "native:deleteduplicategeometries": "删除重复几何要素",
        "native:polygonstolines": "将面边界转换为线",
        "native:simplifygeometries": "简化要素几何",
    }

    for operator_id, action in expected_actions.items():
        record = _record()
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert action in result["task_description"], operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_stable110_direct_chain_operators_have_deterministic_semantics() -> None:
    expected_actions = {
        "native:explodelines": "将线要素按顶点拆分为独立线段",
        "native:lineintersections": "计算两个线图层的交点",
    }

    for operator_id, action in expected_actions.items():
        record = _record()
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert action in result["task_description"], operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_exact_existing_l3_operators_have_deterministic_semantics() -> None:
    expected_actions = {
        "native:rasterize": "将矢量要素转换为栅格单元",
        "native:extractwithindistance": "提取距参考图层指定距离内的要素",
        "saga:polygonclipping": "使用多边形裁剪多边形要素",
        "qgis:variabledistancebuffer": "按要素字段中的距离创建缓冲区",
        "native:randompointsinpolygons": "在多边形内生成随机采样点",
        "native:extractzvalues": "提取要素几何的 Z 值",
        "native:pointonsurface": "为每个要素生成内部点",
        "native:randompointsinextent": "在指定范围内生成随机采样点",
        "native:generatepointspixelcentroidsinsidepolygons": (
            "在多边形内的栅格像元中心生成采样点"
        ),
    }

    for operator_id, action in expected_actions.items():
        record = _record()
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert action in result["task_description"], operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_reviewed_standard_provider_equivalents_have_deterministic_semantics() -> None:
    for operator_id in (
        "grass7:r.neighbors",
        "saga:featuresbuffer",
        "saga:polygonselfintersection",
    ):
        record = _record()
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_advanced_python_field_calculator_remains_deferred() -> None:
    record = _record()
    record["operator_ids"] = ["qgis:advancedpythonfieldcalculator"]
    record["dependency_edges"] = []

    result = build_task_description(record)

    assert result["description_fidelity_status"] == "deferred"
    assert result["known_omissions"] == [
        "missing_operator_phrase:qgis:advancedpythonfieldcalculator"
    ]


def test_split_pool_catalog_operators_have_deterministic_semantics() -> None:
    expected_actions = {
        "native:zonalstatistics": "按多边形分区计算栅格统计量并更新图层",
        "native:fillnodata": "使用指定值填充栅格无数据单元",
        "gdal:slope": "从高程栅格计算坡度",
        "saga:fillsinksxxlwangliu": "使用 Wang-Liu 方法填充高程洼地",
        "gdal:aspect": "从高程栅格计算坡向",
        "qgis:selectbyattribute": "按属性条件选择矢量要素",
        "native:cellstatistics": "按像元位置计算多栅格统计量",
        "native:removenullgeometries": "移除无几何的矢量要素",
        "gdal:convertformat": "转换矢量数据文件格式",
        "native:selectbylocation": "按空间关系选择矢量要素",
    }

    for operator_id, action in expected_actions.items():
        record = _record(scope="local_subworkflow")
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert result["description_policy"] == "deterministic_operator_dag_zh_v5"
        assert action in result["task_description"], operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_generation_preserves_frozen_chain_and_audit_passes() -> None:
    record = _record()
    result = build_task_description(record)
    audit = audit_task_description(record, result)

    assert result["frozen_operator_ids"] == record["operator_ids"]
    assert result["frozen_dependency_edges"] == record["dependency_edges"]
    assert result["frozen_l3_chain"] == record["mapped_l3_chain"]
    assert audit["description_fidelity_passed"] is True
    assert audit["description_fidelity_reasons"] == []


def test_recovery_fanin_catalog_operators_have_deterministic_semantics() -> None:
    expected_actions = {
        "qgis:statisticsbycategories": "按分类字段汇总数值统计量",
        "native:symmetricaldifference": "计算两个图层的对称差异",
        "native:savefeatures": "保存矢量要素到文件",
        "native:saveselectedfeatures": "仅保存输入图层中已选中的矢量要素",
        "native:createspatialindex": "为矢量图层创建空间索引",
        "native:snapgeometries": "按容差将输入几何捕捉到参考图层",
        "native:extractbyextent": "按指定范围提取要素",
    }

    for operator_id, action in expected_actions.items():
        record = _record(scope="local_subworkflow")
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        result = build_task_description(record)
        audit = audit_task_description(record, result)

        assert result["description_fidelity_status"] == "candidate", operator_id
        assert action in result["task_description"], operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_extracts_only_whitelisted_literal_parameter_facts() -> None:
    source = """
import processing
buffered = processing.run("native:buffer", {
    "INPUT": input_layer,
    "DISTANCE": 10,
    "SEGMENTS": 5,
    "OUTPUT": "TEMPORARY_OUTPUT",
})
centroids = processing.run("native:centroids", {
    "INPUT": buffered["OUTPUT"],
    "ALL_PARTS": False,
    "OUTPUT": "TEMPORARY_OUTPUT",
})
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 8},
            {"operator_id": "native:centroids", "line_start": 9, "line_end": 13},
        ],
    )

    assert facts == [
        {"DISTANCE": 10, "SEGMENTS": 5},
        {"ALL_PARTS": False},
    ]


def test_parameter_facts_make_description_specific_without_mutating_chain() -> None:
    record = _record()
    record["parameter_facts"] = [
        {"DISTANCE": 10, "SEGMENTS": 5},
        {"ALL_PARTS": False},
    ]

    result = build_task_description(record)
    audit = audit_task_description(record, result)

    assert "距离为 10" in result["task_description"]
    assert "分段数为 5" in result["task_description"]
    assert "为每个要素生成单一质心" in result["task_description"]
    assert audit["description_fidelity_passed"] is True


def test_empty_dissolve_field_list_is_rendered_semantically() -> None:
    record = _record()
    record["operator_ids"] = ["native:dissolve", "gdal:polygonize"]
    record["parameter_facts"] = [{"FIELD": []}, {"BAND": 1, "FIELD": "DN"}]

    result = build_task_description(record)

    assert "不按字段分组" in result["task_description"]
    assert "字段为 ，" not in result["task_description"]
    assert "对输入数据将" not in result["task_description"]


def test_extracts_nearest_prior_static_parameter_dict_in_same_scope() -> None:
    source = """
import processing

def run(input_layer):
    parameters = {"FORMULA": "A * 1", "NO_DATA": -1, "RTYPE": 1}

    def nested():
        parameters = {"FORMULA": "nested", "NO_DATA": -2, "RTYPE": 2}
        return processing.run("gdal:rastercalculator", parameters)

    parameters = {"FORMULA": "A * 2", "NO_DATA": -9999, "RTYPE": 5}
    return processing.run("gdal:rastercalculator", parameters)
"""

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "gdal:rastercalculator",
                "line_start": 12,
                "line_end": 12,
            }
        ],
    )

    assert facts == [{"FORMULA": "A * 2", "NO_DATA": -9999, "RTYPE": 5}]


def test_parameter_dict_resolution_does_not_cross_nested_function_scope() -> None:
    source = """
import processing

def outer(input_layer):
    parameters = {"FORMULA": "outer", "NO_DATA": -9999, "RTYPE": 5}

    def nested():
        return processing.run("gdal:rastercalculator", parameters)

    return nested()
"""

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "gdal:rastercalculator",
                "line_start": 8,
                "line_end": 8,
            }
        ],
    )

    assert facts == [{}]


def test_parameter_dict_resolution_fails_closed_after_dynamic_reassignment() -> None:
    source = """
import processing

def run():
    parameters = {"FORMULA": "stale", "NO_DATA": -1, "RTYPE": 1}
    parameters = build_parameters()
    return processing.run("gdal:rastercalculator", parameters)
"""

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "gdal:rastercalculator",
                "line_start": 7,
                "line_end": 7,
            }
        ],
    )

    assert facts == [{}]


def test_operator_matching_accepts_only_conservative_provider_aliases() -> None:
    cases = [
        (
            "qgis:selectbylocation",
            "native:selectbylocation",
            {"PREDICATE": [0, 6], "METHOD": 1},
        ),
        (
            "gdalogr:rasterize",
            "gdal:rasterize",
            {"FIELD": "height", "BURN": 1, "UNITS": 0},
        ),
        (
            "gdal:rasterize",
            "gdalogr:rasterize",
            {"FIELD": "height", "BURN": 1, "UNITS": 0},
        ),
        (
            "native:rastercalc",
            "qgis:rastercalculator",
            {"FORMULA": "A * 2", "NO_DATA": -9999, "RTYPE": 5},
        ),
        (
            "native:modelerrastercalc",
            "qgis:rastercalculator",
            {"FORMULA": "A + B", "NO_DATA": -9999, "RTYPE": 5},
        ),
    ]

    for source_operator, call_site_operator, parameters in cases:
        source = (
            "import processing\n"
            f"processing.run({source_operator!r}, {parameters!r})\n"
        )
        facts = extract_literal_parameter_facts(
            source,
            call_sites=[
                {
                    "operator_id": call_site_operator,
                    "line_start": 2,
                    "line_end": 2,
                }
            ],
        )

        assert facts == [parameters], (source_operator, call_site_operator)


def test_required_parameter_whitelists_cover_qgis_provider_aliases() -> None:
    cases = [
        ("qgis:rastercalculator", {"FORMULA": "A + B", "NO_DATA": -9999, "RTYPE": 5}),
        ("qgis:rasterize", {"FIELD": "height", "BURN": 2, "UNITS": 1}),
        ("qgis:extractbyextent", {"CLIP": False}),
        ("qgis:selectbylocation", {"PREDICATE": [0, 6], "METHOD": 1}),
        ("qgis:zonalstatistics", {"STATS": [2, 3]}),
    ]

    for operator_id, parameters in cases:
        source = (
            "import processing\n"
            f"processing.run({operator_id!r}, {parameters!r})\n"
        )

        assert extract_literal_parameter_facts(
            source,
            call_sites=[
                {"operator_id": operator_id, "line_start": 2, "line_end": 2}
            ],
        ) == [parameters]


def test_required_parameter_facts_are_rendered_in_chinese_description() -> None:
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = [
        "native:selectbylocation",
        "native:zonalstatistics",
        "native:extractbyextent",
        "gdal:rastercalculator",
        "gdal:rasterize",
    ]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"] * 5
    record["parameter_facts"] = [
        {"PREDICATE": [0, 6], "METHOD": 1},
        {"STATS": [2, 3]},
        {"CLIP": False},
        {"FORMULA": "A * 2", "NO_DATA": -9999, "RTYPE": 5},
        {"FIELD": "height", "BURN": 2, "UNITS": 1},
    ]

    result = build_task_description(record)
    audit = audit_task_description(record, result)

    description = result["task_description"]
    assert "空间关系为 0、6" in description
    assert "选择方式为 1" in description
    assert "统计量为 2、3" in description
    assert "按指定范围提取要素" in description
    assert "CLIP 为否，不裁剪几何" in description
    assert "提取或裁剪" not in description
    assert "计算公式为 A * 2" in description
    assert "字段为 height" in description
    assert audit["description_fidelity_passed"] is True


def test_audit_fails_when_frozen_safe_parameter_value_is_missing() -> None:
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["gdal:rastercalculator"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = [
        {"FORMULA": "A * 2", "NO_DATA": -9999, "RTYPE": 5}
    ]
    candidate = build_task_description(record)
    candidate["task_description"] = candidate["task_description"].replace("A * 2", "")

    audit = audit_task_description(record, candidate)

    assert audit["description_fidelity_passed"] is False
    assert (
        "parameter_value_not_covered:0:gdal:rastercalculator:FORMULA"
        in audit["description_fidelity_reasons"]
    )


def test_empty_safe_parameter_list_is_rendered_and_audited() -> None:
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:selectbylocation"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = [{"PREDICATE": []}]

    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert "空间关系为 空列表" in candidate["task_description"]
    assert audit["description_fidelity_passed"] is True


def test_warp_reproject_does_not_claim_alignment_without_parameter_evidence() -> None:
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["gdal:warpreproject"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = [{}]

    result = build_task_description(record)

    assert "重投影栅格" in result["task_description"]
    assert "对齐" not in result["task_name"]
    assert "对齐" not in result["task_description"]

    record["parameter_facts"] = [{"TARGET_RESOLUTION": 30}]
    result_with_resolution = build_task_description(record)

    assert "目标分辨率为 30" in result_with_resolution["task_description"]


def test_parameter_mapping_mutations_invalidate_prior_static_facts() -> None:
    sources = [
        """
import processing
parameters = {"FORMULA": "stale", "NO_DATA": -1, "RTYPE": 1}
parameters["FORMULA"] = formula
processing.run("gdal:rastercalculator", parameters)
""",
        """
import processing
parameters = {"FORMULA": "stale", "NO_DATA": -1, "RTYPE": 1}
parameters.update({"FORMULA": formula})
processing.run("gdal:rastercalculator", parameters)
""",
        """
import processing
parameters = {"FORMULA": "stale", "NO_DATA": -1, "RTYPE": 1}
parameters |= {"FORMULA": formula}
processing.run("gdal:rastercalculator", parameters)
""",
        """
import processing
parameters = {"FORMULA": "stale", "NO_DATA": -1, "RTYPE": 1}
alias = parameters
alias["FORMULA"] = formula
processing.run("gdal:rastercalculator", parameters)
""",
        """
import processing
parameters = {"FORMULA": "stale", "NO_DATA": -1, "RTYPE": 1}
alias = parameters
alias.update({"FORMULA": formula})
processing.run("gdal:rastercalculator", parameters)
""",
    ]

    for source in sources:
        call_line = len(source.splitlines())
        facts = extract_literal_parameter_facts(
            source,
            call_sites=[
                {
                    "operator_id": "gdal:rastercalculator",
                    "line_start": call_line,
                    "line_end": call_line,
                }
            ],
        )
        record = _record(scope="local_subworkflow")
        record["operator_ids"] = ["gdal:rastercalculator"]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]
        record["parameter_facts"] = facts

        candidate = build_task_description(record)
        audit = audit_task_description(record, candidate)

        assert facts == [{}]
        assert candidate["description_fidelity_status"] == "deferred"
        assert any(
            "parameter_mapping_mutated" in reason
            for reason in candidate["known_omissions"]
        )
        assert audit["description_fidelity_passed"] is False


def test_dynamic_safe_parameter_is_deferred_end_to_end() -> None:
    source = """
import processing
processing.run("gdal:rastercalculator", {
    "FORMULA": formula,
    "NO_DATA": -9999,
    "RTYPE": 5,
})
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "gdal:rastercalculator",
                "line_start": 3,
                "line_end": 7,
            }
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["gdal:rastercalculator"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert facts == [{"NO_DATA": -9999, "RTYPE": 5}]
    assert candidate["description_fidelity_status"] == "deferred"
    assert (
        "parameter_resolution:0:dynamic_safe_parameter:FORMULA"
        in candidate["known_omissions"]
    )
    assert audit["description_fidelity_passed"] is False

    candidate["description_fidelity_status"] = "candidate"
    candidate["task_description"] = (
        "在该局部工作流中，对输入数据执行栅格计算"
        "（无数据值为 -9999，输出数据类型为 5），"
        "得到此 Processing 链的结果。"
    )
    forged_audit = audit_task_description(record, candidate)

    assert (
        "parameter_resolution_deferred:0:dynamic_safe_parameter:FORMULA"
        in forged_audit["description_fidelity_reasons"]
    )

    persisted = json.loads(json.dumps({**record, **candidate}))
    persisted_audit = audit_task_description(persisted, persisted)

    assert (
        "parameter_resolution_deferred:0:dynamic_safe_parameter:FORMULA"
        in persisted_audit["description_fidelity_reasons"]
    )


def test_deletecolumn_function_parameter_is_rendered_without_inventing_value() -> None:
    source = """
import processing

def delete_columns(layer, dropfields):
    return processing.run("qgis:deletecolumn", {
        "INPUT": layer,
        "COLUMN": dropfields,
        "OUTPUT": "memory:",
    })
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "native:deletecolumn",
                "line_start": 5,
                "line_end": 9,
            }
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:deletecolumn"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert facts == [
        {
            "COLUMN": {
                "kind": "source_function_parameter",
                "name": "dropfields",
            }
        }
    ]
    assert "字段由调用输入指定" in candidate["task_description"]
    assert audit["description_fidelity_passed"] is True


def test_legacy_zonalstatistics_statistics_parameter_is_rendered() -> None:
    source = """
import processing
processing.run("qgis:zonalstatistics", {
    "INPUT_RASTER": raster,
    "INPUT_VECTOR": zones,
    "STATISTICS": [5, 6],
})
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "native:zonalstatistics",
                "line_start": 3,
                "line_end": 7,
            }
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:zonalstatistics"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert facts == [{"STATISTICS": [5, 6]}]
    assert "统计量为 5、6" in candidate["task_description"]
    assert audit["description_fidelity_passed"] is True


def test_dynamic_join_fields_are_deferred_end_to_end() -> None:
    source = """
import processing
processing.run("native:joinattributestable", {
    "INPUT": left,
    "FIELD": left_key,
    "INPUT_2": right,
    "FIELD_2": right_key,
})
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "native:joinattributestable",
                "line_start": 3,
                "line_end": 8,
            }
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:joinattributestable"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)

    assert facts == [{}]
    assert candidate["description_fidelity_status"] == "deferred"
    assert {
        "parameter_resolution:0:dynamic_safe_parameter:FIELD",
        "parameter_resolution:0:dynamic_safe_parameter:FIELD_2",
    }.issubset(candidate["known_omissions"])


def test_dynamic_non_safe_parameter_does_not_block_description() -> None:
    source = """
import processing
processing.run("native:buffer", {
    "INPUT": input_layer,
    "OUTPUT": output_path,
})
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 6}
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:buffer"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)

    assert facts == [{}]
    assert candidate["description_fidelity_status"] == "candidate"


def test_audit_binds_parameter_details_to_their_ordinal_clause() -> None:
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:buffer", "native:buffer"]
    record["dependency_edges"] = [[0, 1]]
    record["mapped_l3_chain"] = ["L3_TEST", "L3_TEST"]
    record["parameter_facts"] = [{"DISTANCE": 10}, {"DISTANCE": 10}]
    candidate = build_task_description(record)
    first_clause, separator, second_clause = candidate["task_description"].partition(
        "；随后"
    )
    candidate["task_description"] = separator.join(
        [first_clause, second_clause.replace("（距离为 10）", "", 1)]
    )

    audit = audit_task_description(record, candidate)

    assert audit["description_fidelity_passed"] is False
    assert (
        "parameter_value_not_covered:1:native:buffer:DISTANCE"
        in audit["description_fidelity_reasons"]
    )


def test_conditional_or_loop_assignment_does_not_dominate_outer_call() -> None:
    sources = [
        """
import processing
if enabled:
    parameters = {"FORMULA": "conditional", "NO_DATA": -1, "RTYPE": 1}
processing.run("gdal:rastercalculator", parameters)
""",
        """
import processing
for item in items:
    parameters = {"FORMULA": "loop", "NO_DATA": -1, "RTYPE": 1}
processing.run("gdal:rastercalculator", parameters)
""",
    ]

    for source in sources:
        call_line = len(source.splitlines())
        facts = extract_literal_parameter_facts(
            source,
            call_sites=[
                {
                    "operator_id": "gdal:rastercalculator",
                    "line_start": call_line,
                    "line_end": call_line,
                }
            ],
        )
        record = _record(scope="local_subworkflow")
        record["operator_ids"] = ["gdal:rastercalculator"]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]
        record["parameter_facts"] = facts

        candidate = build_task_description(record)

        assert facts == [{}]
        assert candidate["description_fidelity_status"] == "deferred"
        assert any(
            "non_dominating_parameter_assignment" in reason
            for reason in candidate["known_omissions"]
        )


def test_formula_and_expression_preserve_literal_whitespace() -> None:
    formula = "A  +  B"
    expression = "kind  =  'primary road'"
    source = (
        "import processing\n"
        f"processing.run('gdal:rastercalculator', {{'FORMULA': {formula!r}}})\n"
        f"processing.run('native:extractbyexpression', {{'EXPRESSION': {expression!r}}})\n"
    )

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "gdal:rastercalculator",
                "line_start": 2,
                "line_end": 2,
            },
            {
                "operator_id": "native:extractbyexpression",
                "line_start": 3,
                "line_end": 3,
            },
        ],
    )

    assert facts == [{"FORMULA": formula}, {"EXPRESSION": expression}]


def test_runtime_workflow_parameter_subscript_is_rendered_without_inventing_value() -> None:
    source = """
import processing

def processAlgorithm(self, parameters, context, feedback):
    return processing.run("native:buffer", {
        "INPUT": parameters["INPUT"],
        "DISTANCE": parameters["DISTANCE"],
        "OUTPUT": parameters["OUTPUT"],
    })
"""
    call_line = next(
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if "processing.run" in line
    )
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "native:buffer",
                "line_start": call_line,
                "line_end": call_line + 4,
            }
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:buffer"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert facts == [
        {
            "DISTANCE": {
                "kind": "runtime_workflow_parameter",
                "name": "DISTANCE",
            }
        }
    ]
    assert "距离由任务输入指定" in candidate["task_description"]
    assert audit["description_fidelity_passed"] is True


def test_parameter_as_assignment_is_a_verified_runtime_workflow_parameter() -> None:
    source = """
import processing

def processAlgorithm(self, parameters, context, feedback):
    distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
    return processing.run("native:buffer", {
        "INPUT": parameters["INPUT"],
        "DISTANCE": distance,
        "OUTPUT": parameters["OUTPUT"],
    })
"""
    call_line = next(
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if "processing.run" in line
    )

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {
                "operator_id": "native:buffer",
                "line_start": call_line,
                "line_end": call_line + 4,
            }
        ],
    )

    assert facts == [
        {
            "DISTANCE": {
                "kind": "runtime_workflow_parameter",
                "name": "DISTANCE",
            }
        }
    ]


def test_source_function_parameter_is_rendered_without_inventing_value() -> None:
    source = """
import processing

def export_raster(layer, field):
    processing.run("gdal:rasterize", {
        "INPUT": layer,
        "FIELD": field,
        "BURN": 0,
        "UNITS": 1,
        "OUTPUT": "memory:",
    })
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "gdal:rasterize", "line_start": 5, "line_end": 11}
        ],
    )
    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["gdal:rasterize"]
    record["dependency_edges"] = []
    record["mapped_l3_chain"] = ["L3_TEST"]
    record["parameter_facts"] = facts

    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert facts == [
        {
            "FIELD": {
                "kind": "source_function_parameter",
                "name": "field",
            },
            "BURN": 0,
            "UNITS": 1,
        }
    ]
    assert "字段由调用输入指定" in candidate["task_description"]
    assert audit["description_fidelity_passed"] is True


def test_description_only_operator_families_have_deterministic_semantics() -> None:
    operators = [
        "native:hillshade",
        "native:ruggednessindex",
        "native:aspect",
        "native:addxyfields",
        "native:boundingboxes",
        "qgis:joinbylocationsummary",
        "qgis:basicstatisticsforfields",
        "native:setzfromraster",
        "native:splitlinesbylength",
        "grass7:r.lake",
        "native:pointstopath",
        "native:calculatevectoroverlaps",
        "native:aggregate",
        "native:createpointslayerfromtable",
        "native:multiringconstantbuffer",
        "native:setlayerstyle",
        "gdal:dissolve",
    ]

    for operator_id in operators:
        record = _record()
        record["operator_ids"] = [operator_id]
        record["dependency_edges"] = []
        record["mapped_l3_chain"] = ["L3_TEST"]

        candidate = build_task_description(record)
        audit = audit_task_description(record, candidate)

        assert candidate["description_fidelity_status"] == "candidate", operator_id
        assert audit["description_fidelity_passed"] is True, operator_id


def test_dominating_literal_aliases_are_recovered_as_parameter_facts() -> None:
    source = """
import processing

target_crs = "EPSG:3857"
distance = 250
reprojected = processing.run("native:reprojectlayer", {
    "TARGET_CRS": target_crs,
    "OUTPUT": "memory:",
})
processing.run("native:buffer", {
    "INPUT": reprojected["OUTPUT"],
    "DISTANCE": distance,
    "OUTPUT": "memory:",
})
"""

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "native:reprojectlayer", "line_start": 6, "line_end": 9},
            {"operator_id": "native:buffer", "line_start": 10, "line_end": 14},
        ],
    )

    assert facts == [{"TARGET_CRS": "EPSG:3857"}, {"DISTANCE": 250}]


def test_dominating_derived_values_are_rendered_without_inventing_values() -> None:
    source = """
import processing

drop_fields = [field for field in all_fields if field not in fields_to_keep]
processing.run("native:deletecolumn", {
    "INPUT": layer,
    "COLUMN": drop_fields,
    "OUTPUT": "memory:",
})
processing.run("native:fieldcalculator", {
    "INPUT": layer,
    "FIELD_NAME": "area_text",
    "FIELD_TYPE": 2,
    "FIELD_LENGTH": 20,
    "FORMULA": str(area),
    "OUTPUT": "memory:",
})
"""
    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "native:deletecolumn", "line_start": 5, "line_end": 9},
            {"operator_id": "native:fieldcalculator", "line_start": 10, "line_end": 17},
        ],
    )
    derived = {"kind": "derived_workflow_value"}
    assert facts == [
        {"COLUMN": derived},
        {
            "FIELD_NAME": "area_text",
            "FIELD_TYPE": 2,
            "FIELD_LENGTH": 20,
            "FORMULA": derived,
        },
    ]

    record = _record(scope="local_subworkflow")
    record["operator_ids"] = ["native:deletecolumn", "native:fieldcalculator"]
    record["dependency_edges"] = [[0, 1]]
    record["mapped_l3_chain"] = ["L3_TEST", "L3_TEST"]
    record["parameter_facts"] = facts
    candidate = build_task_description(record)
    audit = audit_task_description(record, candidate)

    assert candidate["description_policy"] == "deterministic_operator_dag_zh_v5"
    assert candidate["task_description"].count("由工作流计算指定") == 2
    assert audit["description_fidelity_passed"] is True


def test_explicit_empty_default_parameters_do_not_block_description() -> None:
    source = """
import processing

processing.run("native:reprojectlayer", {
    "OPERATION": "",
    "OUTPUT": "memory:",
})
processing.run("native:intersection", {
    "INPUT_FIELDS": "",
    "OVERLAY_FIELDS": "",
    "OUTPUT": "memory:",
})
"""

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "native:reprojectlayer", "line_start": 4, "line_end": 7},
            {"operator_id": "native:intersection", "line_start": 8, "line_end": 13},
        ],
    )

    assert facts == [{}, {}]
    assert [fact.resolution_status for fact in facts] == ["resolved", "resolved"]


def test_empty_formula_remains_fail_closed() -> None:
    source = """
import processing

processing.run("native:fieldcalculator", {
    "FORMULA": "",
    "OUTPUT": "memory:",
})
"""

    facts = extract_literal_parameter_facts(
        source,
        call_sites=[
            {"operator_id": "native:fieldcalculator", "line_start": 4, "line_end": 7}
        ],
    )

    assert facts == [{}]
    assert facts[0].resolution_status == "deferred"
    assert facts[0].resolution_reasons == ["dynamic_safe_parameter:FORMULA"]
