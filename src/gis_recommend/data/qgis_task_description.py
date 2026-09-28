"""Deterministic, fail-closed task text for verified QGIS Processing DAGs."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from typing import Any
import warnings


DESCRIPTION_POLICY = "deterministic_operator_dag_zh_v5"
ALLOWED_SCOPES = {"whole_processing_scope", "local_subworkflow"}
FORBIDDEN_LEGACY_TERMS = (
    "source repo",
    "repository",
    "repo",
    "source code",
    "function",
    " ui ",
    "仓库",
    "源码",
    "函数",
    "界面",
    "导出",
)
_UNRESOLVED_LITERAL = object()
_RUNTIME_WORKFLOW_PARAMETER_KIND = "runtime_workflow_parameter"
_SOURCE_FUNCTION_PARAMETER_KIND = "source_function_parameter"
_DERIVED_WORKFLOW_VALUE_KIND = "derived_workflow_value"
_OMITTED_EMPTY_PARAMETER_KEYS = {"INPUT_FIELDS", "OPERATION", "OVERLAY_FIELDS"}


class _ResolvedParameterFacts(dict[str, Any]):
    """A dict-compatible fact result carrying fail-closed resolution evidence."""

    def __init__(
        self,
        values: Mapping[str, Any] | None = None,
        *,
        status: str = "resolved",
        reasons: Sequence[str] = (),
    ) -> None:
        super().__init__(values or {})
        self.resolution_status = status
        self.resolution_reasons = list(reasons)


# Each anchor is intentionally short and must occur verbatim in generated text.
OPERATOR_SEMANTICS: dict[str, dict[str, str]] = {
    "grass7:r.neighbors": {
        "action": "按移动窗口计算栅格邻域统计量",
        "title": "计算栅格邻域统计",
        "result": "邻域统计栅格",
    },
    "gdal:aspect": {"action": "从高程栅格计算坡向", "title": "计算坡向", "result": "坡向栅格"},
    "gdal:dissolve": {"action": "融合矢量要素", "title": "融合矢量要素", "result": "融合后的矢量图层"},
    "gdal:cliprasterbymasklayer": {
        "action": "按矢量掩膜裁剪栅格",
        "title": "掩膜裁剪栅格",
        "result": "裁剪后的栅格",
    },
    "gdal:convertformat": {
        "action": "转换矢量数据文件格式",
        "title": "转换矢量格式",
        "result": "格式转换后的矢量数据",
    },
    "gdal:extractprojection": {
        "action": "提取栅格投影并写入世界文件",
        "title": "提取栅格投影",
        "result": "栅格投影世界文件",
    },
    "gdal:fillnodata": {
        "action": "插值填充栅格无数据区域",
        "title": "填充无数据区域",
        "result": "填充后的栅格",
    },
    "gdal:merge": {"action": "合并多个栅格文件", "title": "合并栅格", "result": "合并后的栅格"},
    "gdal:polygonize": {"action": "转换栅格为矢量面", "title": "栅格面化", "result": "矢量面结果"},
    "gdal:rastercalculator": {"action": "执行栅格计算", "title": "栅格计算", "result": "计算后的栅格"},
    "gdal:rasterize": {"action": "将矢量几何栅格化", "title": "矢量栅格化", "result": "栅格化结果"},
    "gdal:slope": {"action": "从高程栅格计算坡度", "title": "计算坡度", "result": "坡度栅格"},
    "gdal:translate": {"action": "转换栅格数据格式或范围", "title": "转换栅格", "result": "转换后的栅格"},
    "gdal:warpreproject": {"action": "重投影栅格", "title": "重投影栅格", "result": "重投影后的栅格"},
    "native:addautoincrementalfield": {
        "action": "添加自增整数字段",
        "title": "添加自增字段",
        "result": "带自增字段的图层",
    },
    "native:assignprojection": {"action": "为图层指定坐标参考系", "title": "指定坐标系", "result": "已指定坐标系的图层"},
    "native:addxyfields": {
        "action": "向要素添加 X 和 Y 坐标字段",
        "title": "添加坐标字段",
        "result": "带坐标字段的图层",
    },
    "native:aspect": {"action": "从高程栅格计算坡向", "title": "计算坡向", "result": "坡向栅格"},
    "native:boundingboxes": {
        "action": "为输入要素创建边界框",
        "title": "创建边界框",
        "result": "要素边界框",
    },
    "native:buffer": {"action": "创建缓冲区", "title": "创建缓冲区", "result": "缓冲区结果"},
    "native:centroids": {"action": "提取质心", "title": "提取质心", "result": "质心结果"},
    "native:cellstatistics": {
        "action": "按像元位置计算多栅格统计量",
        "title": "多栅格像元统计",
        "result": "像元统计栅格",
    },
    "native:clip": {
        "action": "使用多边形图层裁剪矢量要素",
        "title": "裁剪矢量图层",
        "result": "裁剪后的矢量图层",
    },
    "native:creategrid": {
        "action": "创建规则矢量网格",
        "title": "创建矢量网格",
        "result": "矢量网格",
    },
    "native:deletecolumn": {"action": "删除指定字段", "title": "删除字段", "result": "删除字段后的图层"},
    "native:deleteduplicategeometries": {
        "action": "删除重复几何要素",
        "title": "删除重复几何",
        "result": "去除重复几何后的图层",
    },
    "native:difference": {"action": "计算空间差异", "title": "计算差异", "result": "差异结果"},
    "native:dissolve": {"action": "融合矢量要素", "title": "融合要素", "result": "融合结果"},
    "native:extractbyattribute": {"action": "按属性条件筛选要素", "title": "属性筛选", "result": "筛选结果"},
    "native:extractbyexpression": {"action": "按表达式筛选要素", "title": "表达式筛选", "result": "筛选结果"},
    "native:extractbyextent": {
        "action": "按指定范围提取要素",
        "title": "按范围提取要素",
        "result": "范围内的要素",
    },
    "native:extractbylocation": {"action": "按空间关系筛选要素", "title": "空间筛选", "result": "筛选结果"},
    "native:extractwithindistance": {
        "action": "提取距参考图层指定距离内的要素",
        "title": "按距离提取要素",
        "result": "距离范围内的要素",
    },
    "native:extractvertices": {"action": "提取要素顶点", "title": "提取顶点", "result": "顶点结果"},
    "native:extractzvalues": {
        "action": "提取要素几何的 Z 值",
        "title": "提取 Z 值",
        "result": "带 Z 值属性的要素",
    },
    "native:explodelines": {
        "action": "将线要素按顶点拆分为独立线段",
        "title": "拆分线段",
        "result": "独立线段",
    },
    "native:fieldcalculator": {"action": "计算字段值", "title": "计算字段", "result": "更新字段的图层"},
    "native:fillnodata": {
        "action": "使用指定值填充栅格无数据单元",
        "title": "填充无数据单元",
        "result": "无缺失单元的栅格",
    },
    "native:fixgeometries": {"action": "修复无效几何", "title": "修复几何", "result": "修复后的图层"},
    "native:generatepointspixelcentroidsinsidepolygons": {
        "action": "在多边形内的栅格像元中心生成采样点",
        "title": "生成像元中心采样点",
        "result": "多边形内的像元中心采样点",
    },
    "native:hillshade": {
        "action": "根据高程和光照参数生成阴影地形栅格",
        "title": "生成阴影地形",
        "result": "阴影地形栅格",
    },
    "native:intersection": {"action": "计算图层相交结果", "title": "计算相交", "result": "相交结果"},
    "native:joinattributesbylocation": {"action": "按空间位置连接属性", "title": "空间连接属性", "result": "属性连接结果"},
    "native:joinattributestable": {
        "action": "按指定字段连接属性表",
        "title": "连接属性表",
        "result": "属性表连接结果",
    },
    "native:lineintersections": {
        "action": "计算两个线图层的交点",
        "title": "计算线交点",
        "result": "线交点",
    },
    "native:mergevectorlayers": {
        "action": "合并多个矢量图层",
        "title": "合并矢量图层",
        "result": "合并后的矢量图层",
    },
    "native:multiparttosingleparts": {"action": "拆分多部件要素为单部件", "title": "拆分多部件", "result": "单部件结果"},
    "native:multiringconstantbuffer": {
        "action": "按固定间距创建多环缓冲区",
        "title": "创建多环缓冲区",
        "result": "多环缓冲区",
    },
    "native:polygonize": {"action": "转换线条为面", "title": "线条面化", "result": "面状结果"},
    "native:polygonstolines": {
        "action": "将面边界转换为线",
        "title": "面转线",
        "result": "边界线结果",
    },
    "native:pointonsurface": {
        "action": "为每个要素生成内部点",
        "title": "生成要素内部点",
        "result": "要素内部点",
    },
    "native:randompointsinextent": {
        "action": "在指定范围内生成随机采样点",
        "title": "在范围内生成随机点",
        "result": "范围内的随机采样点",
    },
    "native:randompointsinpolygons": {
        "action": "在多边形内生成随机采样点",
        "title": "在多边形内生成随机点",
        "result": "多边形内的随机采样点",
    },
    "native:rasterize": {
        "action": "将矢量要素转换为栅格单元",
        "title": "矢量栅格化",
        "result": "栅格化结果",
    },
    "native:rastersampling": {"action": "采样栅格值", "title": "采样栅格", "result": "带采样值的图层"},
    "native:rasterlayerstatistics": {
        "action": "计算指定栅格波段的全局统计量",
        "title": "计算栅格全局统计",
        "result": "栅格全局统计结果",
    },
    "native:reclassifybytable": {
        "action": "按分级表重分类栅格",
        "title": "表格重分类栅格",
        "result": "重分类后的栅格",
    },
    "native:refactorfields": {"action": "重构字段结构", "title": "重构字段", "result": "重构字段后的图层"},
    "native:reprojectlayer": {"action": "重投影图层", "title": "重投影图层", "result": "重投影后的图层"},
    "native:removenullgeometries": {
        "action": "移除无几何的矢量要素",
        "title": "移除空几何",
        "result": "移除空几何后的图层",
    },
    "native:retainfields": {"action": "保留指定字段", "title": "保留字段", "result": "保留字段后的图层"},
    "native:renametablefield": {"action": "重命名字段", "title": "重命名字段", "result": "重命名字段后的图层"},
    "native:ruggednessindex": {
        "action": "从高程栅格计算地形崎岖度指数",
        "title": "计算地形崎岖度",
        "result": "地形崎岖度栅格",
    },
    "native:simplifygeometries": {
        "action": "简化要素几何",
        "title": "简化几何",
        "result": "简化后的图层",
    },
    "native:slope": {"action": "计算坡度栅格", "title": "计算坡度", "result": "坡度栅格"},
    "native:selectbylocation": {
        "action": "按空间关系选择矢量要素",
        "title": "空间选择",
        "result": "带空间选择状态的图层",
    },
    "native:setlayerstyle": {
        "action": "为图层应用指定样式",
        "title": "设置图层样式",
        "result": "已设置样式的图层",
    },
    "native:savefeatures": {
        "action": "保存矢量要素到文件",
        "title": "保存矢量要素",
        "result": "已保存的矢量数据",
    },
    "native:saveselectedfeatures": {
        "action": "仅保存输入图层中已选中的矢量要素",
        "title": "保存选中要素",
        "result": "已保存的选中矢量要素",
    },
    "native:createspatialindex": {
        "action": "为矢量图层创建空间索引",
        "title": "创建空间索引",
        "result": "已建立空间索引的矢量图层",
    },
    "native:snapgeometries": {
        "action": "按容差将输入几何捕捉到参考图层",
        "title": "捕捉矢量几何",
        "result": "已捕捉到参考图层的矢量要素",
    },
    "native:symmetricaldifference": {
        "action": "计算两个图层的对称差异",
        "title": "计算对称差异",
        "result": "对称差异结果",
    },
    "native:union": {"action": "计算图层联合", "title": "计算联合", "result": "联合结果"},
    "native:setzfromraster": {
        "action": "按栅格采样值设置要素几何的 Z 坐标",
        "title": "按栅格设置 Z 坐标",
        "result": "带栅格高程 Z 值的要素图层",
    },
    "native:splitlinesbylength": {
        "action": "按最大长度将线要素切分为连续线段",
        "title": "按长度切分线",
        "result": "按指定长度切分后的线图层",
    },
    "grass7:r.lake": {
        "action": "从种子位置按水位和高程栅格模拟湖泊淹没范围",
        "title": "模拟湖泊淹没范围",
        "result": "湖泊或淹没范围栅格",
    },
    "native:pointstopath": {
        "action": "按顺序和分组字段将点要素连接为路径",
        "title": "点连接为路径",
        "result": "由点序列生成的线路径图层",
    },
    "native:calculatevectoroverlaps": {
        "action": "计算输入多边形与叠加图层的重叠面积和比例",
        "title": "计算矢量重叠统计",
        "result": "带重叠面积和比例字段的图层",
    },
    "native:aggregate": {
        "action": "按分组字段聚合要素几何和属性",
        "title": "聚合要素",
        "result": "按分组聚合后的要素图层",
    },
    "native:createpointslayerfromtable": {
        "action": "从表格的 X、Y 坐标字段创建点图层",
        "title": "从表格创建点图层",
        "result": "由坐标字段生成的点图层",
    },
    "native:zonalhistogram": {
        "action": "按多边形分区统计栅格值直方图",
        "title": "分区直方图",
        "result": "带直方图计数字段的图层",
    },
    "native:zonalstatisticsfb": {
        "action": "按多边形分区计算栅格统计量",
        "title": "分区栅格统计",
        "result": "带分区统计字段的图层",
    },
    "native:zonalstatistics": {
        "action": "按多边形分区计算栅格统计量并更新图层",
        "title": "分区统计并更新图层",
        "result": "带分区统计字段的图层",
    },
    "qgis:selectbyattribute": {
        "action": "按属性条件选择矢量要素",
        "title": "属性选择",
        "result": "带属性选择状态的图层",
    },
    "qgis:minimumboundinggeometry": {"action": "计算最小包围几何", "title": "计算最小包围几何", "result": "最小包围几何结果"},
    "qgis:rastercalculator": {"action": "执行栅格计算", "title": "执行栅格计算", "result": "计算后的栅格"},
    "qgis:basicstatisticsforfields": {
        "action": "计算字段的基本统计量",
        "title": "计算字段统计",
        "result": "字段统计结果",
    },
    "qgis:joinbylocationsummary": {
        "action": "按空间位置连接并汇总属性",
        "title": "空间连接汇总",
        "result": "空间连接汇总结果",
    },
    "saga:featuresbuffer": {
        "action": "为矢量要素创建缓冲区",
        "title": "创建要素缓冲区",
        "result": "缓冲区结果",
    },
    "saga:polygonselfintersection": {
        "action": "检查多边形自相交错误",
        "title": "检查多边形自相交",
        "result": "多边形自相交检查结果",
    },
    "saga:splitrgbbands": {
        "action": "拆分栅格的红绿蓝波段",
        "title": "拆分 RGB 波段",
        "result": "红绿蓝波段栅格",
    },
    "saga:fillsinksxxlwangliu": {
        "action": "使用 Wang-Liu 方法填充高程洼地",
        "title": "填充高程洼地",
        "result": "水文连通的高程栅格",
    },
    "qgis:statisticsbycategories": {
        "action": "按分类字段汇总数值统计量",
        "title": "分类汇总统计",
        "result": "分类统计表",
    },
    "qgis:variabledistancebuffer": {
        "action": "按要素字段中的距离创建缓冲区",
        "title": "创建可变距离缓冲区",
        "result": "可变距离缓冲区结果",
    },
    "saga:polygonclipping": {
        "action": "使用多边形裁剪多边形要素",
        "title": "裁剪多边形",
        "result": "裁剪后的多边形要素",
    },
}


SAFE_PARAMETER_KEYS: dict[str, tuple[str, ...]] = {
    "grass7:r.neighbors": ("METHOD", "SIZE"),
    "gdal:polygonize": ("BAND", "FIELD", "EIGHT_CONNECTEDNESS"),
    "gdal:rastercalculator": ("FORMULA", "NO_DATA", "RTYPE"),
    "gdal:rasterize": ("FIELD", "BURN", "UNITS"),
    "gdal:translate": ("NODATA", "DATA_TYPE", "TARGET_CRS"),
    "gdal:warpreproject": ("TARGET_CRS", "RESAMPLING", "TARGET_RESOLUTION"),
    "native:assignprojection": ("CRS",),
    "native:buffer": ("DISTANCE", "SEGMENTS", "END_CAP_STYLE", "JOIN_STYLE", "DISSOLVE"),
    "native:centroids": ("ALL_PARTS",),
    "native:deletecolumn": ("COLUMN",),
    "native:difference": ("GRID_SIZE",),
    "native:dissolve": ("FIELD", "SEPARATE_DISJOINT", "GRID_SIZE"),
    "native:extractbyattribute": ("FIELD", "OPERATOR", "VALUE"),
    "native:extractbyextent": ("CLIP",),
    "native:extractbyexpression": ("EXPRESSION",),
    "native:extractbylocation": ("PREDICATE",),
    "native:extractvertices": ("VERTICES",),
    "native:fieldcalculator": ("FIELD_NAME", "FIELD_TYPE", "FIELD_LENGTH", "FORMULA"),
    "native:fixgeometries": ("METHOD",),
    "native:intersection": ("INPUT_FIELDS", "OVERLAY_FIELDS", "GRID_SIZE"),
    "native:joinattributesbylocation": ("PREDICATE", "JOIN_FIELDS", "METHOD", "DISCARD_NONMATCHING"),
    "native:joinattributestable": ("FIELD", "FIELD_2"),
    "native:multiparttosingleparts": (),
    "native:polygonize": ("KEEP_FIELDS",),
    "native:rastersampling": ("COLUMN_PREFIX",),
    "native:refactorfields": (),
    "native:reprojectlayer": ("TARGET_CRS", "OPERATION"),
    "native:retainfields": ("FIELDS",),
    "native:slope": ("Z_FACTOR",),
    "native:selectbylocation": ("PREDICATE", "METHOD"),
    "native:union": ("GRID_SIZE",),
    "native:zonalstatistics": ("STATS", "STATISTICS"),
    "qgis:minimumboundinggeometry": ("TYPE",),
    "native:modelerrastercalc": ("FORMULA", "NO_DATA", "RTYPE"),
    "native:rastercalc": ("FORMULA", "NO_DATA", "RTYPE"),
    "qgis:extractbyextent": ("CLIP",),
    "qgis:rastercalculator": (
        "EXPRESSION",
        "CELLSIZE",
        "CRS",
        "FORMULA",
        "NO_DATA",
        "RTYPE",
    ),
    "qgis:rasterize": ("FIELD", "BURN", "UNITS"),
    "qgis:selectbylocation": ("PREDICATE", "METHOD"),
    "qgis:zonalstatistics": ("STATS", "STATISTICS"),
    "saga:featuresbuffer": ("DISTANCE", "DISSOLVE"),
    "saga:polygonselfintersection": (),
}


def _ast_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _ast_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _processing_operator_id(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or _ast_name(node.func) != "processing.run":
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return None
    value = str(node.args[0].value).strip().lower()
    return value if ":" in value else None


def _operator_ids_equivalent(left: str, right: str) -> bool:
    left = left.strip().lower()
    right = right.strip().lower()
    if left == right:
        return True
    left_provider, separator, left_slug = left.partition(":")
    right_provider, other_separator, right_slug = right.partition(":")
    if not separator or not other_separator:
        return False
    if left_slug == right_slug and frozenset((left_provider, right_provider)) in {
        frozenset(("qgis", "native")),
        frozenset(("gdalogr", "gdal")),
    }:
        return True
    raster_calculator_aliases = {
        "native:rastercalc",
        "native:modelerrastercalc",
        "qgis:rastercalculator",
    }
    return left in raster_calculator_aliases and right in raster_calculator_aliases


def _safe_parameter_keys(operator_id: str) -> set[str]:
    keys: set[str] = set()
    for known_operator_id, known_keys in SAFE_PARAMETER_KEYS.items():
        if _operator_ids_equivalent(operator_id, known_operator_id):
            keys.update(known_keys)
    return keys


def _safe_literal(
    node: ast.AST, *, preserve_string_whitespace: bool = False
) -> Any:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        if (
            isinstance(node, ast.Call)
            and _ast_name(node.func) in {"QgsCoordinateReferenceSystem", "QgsProperty.fromExpression"}
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
        ):
            value = node.args[0].value
        else:
            return _UNRESOLVED_LITERAL
    if isinstance(value, str):
        if preserve_string_whitespace:
            return value if 0 < len(value) <= 160 else _UNRESOLVED_LITERAL
        stripped = " ".join(value.split())
        return stripped if 0 < len(stripped) <= 160 else _UNRESOLVED_LITERAL
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple)) and len(value) <= 12:
        normalized = []
        for item in value:
            if not isinstance(item, (str, bool, int, float)):
                return _UNRESOLVED_LITERAL
            normalized.append(item)
        return normalized
    return _UNRESOLVED_LITERAL


def _runtime_workflow_parameter_reference(node: ast.AST) -> str | None:
    def parameter_name(value: ast.AST) -> str | None:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value.strip() or None
        if isinstance(value, ast.Attribute):
            return value.attr.strip() or None
        if isinstance(value, ast.Name):
            return value.id.strip() or None
        return None

    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "parameters"
    ):
        return parameter_name(node.slice)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith("parameterAs")
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "parameters"
    ):
        return parameter_name(node.args[1])
    return None


def _source_function_parameter_reference(
    node: ast.AST, *, scope: ast.AST
) -> str | None:
    if not isinstance(node, ast.Name) or not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    ):
        return None
    arguments = scope.args
    names = {
        argument.arg
        for argument in [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]
    }
    if arguments.vararg:
        names.add(arguments.vararg.arg)
    if arguments.kwarg:
        names.add(arguments.kwarg.arg)
    return node.id if node.id in names else None


def _node_position(node: ast.AST, *, end: bool = False) -> tuple[int, int]:
    if end:
        return (
            int(getattr(node, "end_lineno", None) or getattr(node, "lineno", 0)),
            int(getattr(node, "end_col_offset", None) or 0),
        )
    return (int(getattr(node, "lineno", 0)), int(getattr(node, "col_offset", 0)))


def _control_path(
    node: ast.AST,
    *,
    scope: ast.AST,
    parent_by_node: Mapping[ast.AST, ast.AST],
) -> list[tuple[int, str]]:
    control_types = (ast.If, ast.For, ast.AsyncFor, ast.While)
    path: list[tuple[int, str]] = []
    current = node
    while current is not scope and current in parent_by_node:
        parent = parent_by_node[current]
        if isinstance(parent, control_types):
            branch = "unknown"
            for field_name, value in ast.iter_fields(parent):
                if value is current or (isinstance(value, list) and current in value):
                    branch = field_name
                    break
            path.append((id(parent), branch))
        current = parent
    return list(reversed(path))


def _subscript_root_name(node: ast.AST) -> str:
    current = node
    while isinstance(current, ast.Subscript):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def _parameter_mapping_mutation_reason(
    *,
    parameter_name: str,
    assignment: ast.Assign | ast.AnnAssign,
    call: ast.Call,
    scope: ast.AST,
    parent_by_node: Mapping[ast.AST, ast.AST],
) -> str | None:
    aliases = {parameter_name}
    start = _node_position(assignment, end=True)
    end = _node_position(call)
    nodes = sorted(
        (
            node
            for node in ast.walk(scope)
            if start < _node_position(node) < end
        ),
        key=_node_position,
    )
    mutation_methods = {"update", "clear", "pop", "popitem", "setdefault", "__setitem__"}
    for node in nodes:
        current = node
        while current in parent_by_node and parent_by_node[current] is not scope:
            current = parent_by_node[current]
        if current is not node and isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and _subscript_root_name(target) in aliases:
                    return f"parameter_mapping_mutated:subscript:line_{node.lineno}"
            source_alias = node.value.id if isinstance(node.value, ast.Name) else ""
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if source_alias in aliases:
                    aliases.add(target.id)
                elif target.id != parameter_name:
                    aliases.discard(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Subscript) and _subscript_root_name(node.target) in aliases:
                return f"parameter_mapping_mutated:subscript:line_{node.lineno}"
            if isinstance(node.target, ast.Name):
                source_alias = node.value.id if isinstance(node.value, ast.Name) else ""
                if source_alias in aliases:
                    aliases.add(node.target.id)
                elif node.target.id != parameter_name:
                    aliases.discard(node.target.id)
        elif isinstance(node, ast.AugAssign):
            target_name = (
                node.target.id
                if isinstance(node.target, ast.Name)
                else _subscript_root_name(node.target)
            )
            if target_name in aliases:
                return f"parameter_mapping_mutated:augassign:line_{node.lineno}"
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in aliases
            and node.func.attr in mutation_methods
        ):
            return f"parameter_mapping_mutated:{node.func.attr}:line_{node.lineno}"
    return None


def extract_literal_parameter_facts(
    source_text: str, *, call_sites: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Extract a small semantic whitelist of literal facts from selected calls."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError:
        return [
            _ResolvedParameterFacts(
                status="deferred", reasons=["source_syntax_error"]
            )
            for _ in call_sites
        ]
    parent_by_node = {
        child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
    }

    def lexical_scope(node: ast.AST) -> ast.AST:
        current = parent_by_node.get(node)
        while current is not None and not isinstance(
            current,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef),
        ):
            current = parent_by_node.get(current)
        return current or tree

    assignments: dict[tuple[int, str], list[ast.Assign | ast.AnnAssign]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        ):
            names = [node.target.id]
        else:
            continue
        for name in names:
            assignments.setdefault((id(lexical_scope(node)), name), []).append(node)

    def dominating_dynamic_value(
        value_node: ast.AST, *, call: ast.Call
    ) -> ast.AST | None:
        candidate = value_node
        if isinstance(candidate, ast.Name):
            prior_assignments = [
                assignment
                for assignment in assignments.get(
                    (id(lexical_scope(call)), candidate.id), []
                )
                if _node_position(assignment, end=True) <= _node_position(call)
            ]
            if not prior_assignments:
                return None
            nearest = max(prior_assignments, key=lambda item: _node_position(item, end=True))
            assignment_path = _control_path(
                nearest,
                scope=lexical_scope(call),
                parent_by_node=parent_by_node,
            )
            call_path = _control_path(
                call,
                scope=lexical_scope(call),
                parent_by_node=parent_by_node,
            )
            if call_path[: len(assignment_path)] != assignment_path:
                return None
            candidate = nearest.value
        return candidate

    calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _processing_operator_id(node)
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    facts: list[dict[str, Any]] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id") or "").strip().lower()
        start = int(site.get("line_start") or 0)
        end = int(site.get("line_end") or start)
        matching = [
            call
            for call in calls
            if id(call) not in used
            and _operator_ids_equivalent(
                _processing_operator_id(call) or "", operator_id
            )
            and call.lineno <= end
            and int(call.end_lineno or call.lineno) >= start
        ]
        if not matching:
            facts.append(
                _ResolvedParameterFacts(
                    status="deferred", reasons=["processing_call_not_found"]
                )
            )
            continue
        call = min(matching, key=lambda item: abs(item.lineno - start))
        used.add(id(call))
        params = call.args[1] if len(call.args) >= 2 else None
        resolution_reasons: list[str] = []
        if isinstance(params, ast.Name):
            prior_assignments = [
                assignment
                for assignment in assignments.get(
                    (id(lexical_scope(call)), params.id), []
                )
                if (
                    int(assignment.end_lineno or assignment.lineno),
                    int(assignment.end_col_offset or 0),
                )
                <= (call.lineno, call.col_offset)
            ]
            if prior_assignments:
                nearest = max(
                    prior_assignments,
                    key=lambda assignment: (
                        int(assignment.end_lineno or assignment.lineno),
                        int(assignment.end_col_offset or 0),
                    ),
                )
                assignment_path = _control_path(
                    nearest,
                    scope=lexical_scope(call),
                    parent_by_node=parent_by_node,
                )
                call_path = _control_path(
                    call,
                    scope=lexical_scope(call),
                    parent_by_node=parent_by_node,
                )
                if call_path[: len(assignment_path)] != assignment_path:
                    resolution_reasons.append(
                        "non_dominating_parameter_assignment"
                    )
                    params = None
                elif not isinstance(nearest.value, ast.Dict):
                    resolution_reasons.append("dynamic_parameter_mapping")
                    params = None
                else:
                    mutation_reason = _parameter_mapping_mutation_reason(
                        parameter_name=call.args[1].id,
                        assignment=nearest,
                        call=call,
                        scope=lexical_scope(call),
                        parent_by_node=parent_by_node,
                    )
                    if mutation_reason:
                        resolution_reasons.append(mutation_reason)
                        params = None
                    else:
                        params = nearest.value
            else:
                resolution_reasons.append("unresolved_parameter_mapping_reference")
                params = None
        allowed = _safe_parameter_keys(operator_id)
        extracted: dict[str, Any] = {}
        if isinstance(params, ast.Dict):
            for key_node, value_node in zip(params.keys, params.values):
                if key_node is None:
                    if allowed:
                        resolution_reasons.append("dynamic_parameter_mapping_unpack")
                    continue
                if not isinstance(key_node, ast.Constant):
                    if allowed:
                        resolution_reasons.append("dynamic_parameter_key")
                    continue
                key = str(key_node.value).strip().upper()
                if key not in allowed:
                    continue
                value = _safe_literal(
                    value_node,
                    preserve_string_whitespace=key in {"FORMULA", "EXPRESSION"},
                )
                if value is _UNRESOLVED_LITERAL:
                    candidate = dominating_dynamic_value(value_node, call=call)
                    alias_value = (
                        _safe_literal(
                            candidate,
                            preserve_string_whitespace=key in {"FORMULA", "EXPRESSION"},
                        )
                        if candidate is not None
                        else _UNRESOLVED_LITERAL
                    )
                    if alias_value is not _UNRESOLVED_LITERAL:
                        extracted[key] = alias_value
                    elif (
                        key in _OMITTED_EMPTY_PARAMETER_KEYS
                        and isinstance(candidate, ast.Constant)
                        and candidate.value == ""
                    ):
                        continue
                    elif candidate is not None and (
                        name := _runtime_workflow_parameter_reference(candidate)
                    ):
                        extracted[key] = {
                            "kind": _RUNTIME_WORKFLOW_PARAMETER_KIND,
                            "name": name,
                        }
                    elif name := _source_function_parameter_reference(
                        value_node, scope=lexical_scope(call)
                    ):
                        extracted[key] = {
                            "kind": _SOURCE_FUNCTION_PARAMETER_KIND,
                            "name": name,
                        }
                    elif candidate is not None and not isinstance(
                        candidate,
                        (ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict, ast.Name),
                    ):
                        extracted[key] = {"kind": _DERIVED_WORKFLOW_VALUE_KIND}
                    else:
                        resolution_reasons.append(f"dynamic_safe_parameter:{key}")
                else:
                    extracted[key] = value
        elif allowed and not resolution_reasons:
            resolution_reasons.append("dynamic_parameter_mapping")
        facts.append(
            _ResolvedParameterFacts(
                extracted,
                status="deferred" if resolution_reasons else "resolved",
                reasons=resolution_reasons,
            )
        )
    return facts


def _parameter_facts(record: Mapping[str, Any], count: int) -> list[dict[str, Any]]:
    raw = list(record.get("parameter_facts") or [])
    result = [dict(value) if isinstance(value, Mapping) else {} for value in raw[:count]]
    result.extend({} for _ in range(count - len(result)))
    return result


def _parameter_resolution(
    record: Mapping[str, Any], count: int
) -> list[dict[str, Any]]:
    raw_facts = list(record.get("parameter_facts") or [])
    explicit_value = record.get("parameter_fact_resolution")
    if explicit_value is None:
        explicit_value = record.get("frozen_parameter_resolution")
    explicit = list(explicit_value or [])
    resolution: list[dict[str, Any]] = []
    for ordinal in range(count):
        if ordinal < len(explicit) and isinstance(explicit[ordinal], Mapping):
            status = str(explicit[ordinal].get("status") or "resolved")
            reasons = [str(value) for value in explicit[ordinal].get("reasons") or []]
        elif ordinal < len(raw_facts) and isinstance(
            raw_facts[ordinal], _ResolvedParameterFacts
        ):
            status = raw_facts[ordinal].resolution_status
            reasons = list(raw_facts[ordinal].resolution_reasons)
        else:
            status = "resolved"
            reasons = []
        resolution.append({"status": status, "reasons": reasons})
    return resolution


def _display_value(value: Any) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "空列表"
    return str(value)


def _parameter_details(operator_id: str, facts: Mapping[str, Any]) -> list[str]:
    labels = {
        "DISTANCE": "距离",
        "SEGMENTS": "分段数",
        "FIELD": "字段",
        "FIELD_2": "连接表字段",
        "VALUE": "比较值",
        "EXPRESSION": "表达式",
        "TARGET_CRS": "目标坐标系",
        "CRS": "坐标系",
        "FORMULA": "计算公式",
        "FIELD_NAME": "目标字段",
        "FIELDS": "保留字段",
        "JOIN_FIELDS": "连接字段",
        "COLUMN_PREFIX": "采样字段前缀",
        "TARGET_RESOLUTION": "目标分辨率",
        "Z_FACTOR": "高程缩放因子",
        "BAND": "栅格波段",
        "COLUMN": "字段",
        "TYPE": "包围几何类型",
        "PREDICATE": "空间关系",
        "METHOD": "处理方式",
        "STATS": "统计量",
        "STATISTICS": "统计量",
        "NO_DATA": "无数据值",
        "RTYPE": "输出数据类型",
        "BURN": "栅格化值",
        "UNITS": "单位模式",
    }
    details: list[str] = []
    for key in SAFE_PARAMETER_KEYS.get(operator_id, ()):
        if key not in facts:
            continue
        value = facts[key]
        if (
            isinstance(value, Mapping)
            and value.get("kind") == _RUNTIME_WORKFLOW_PARAMETER_KIND
        ):
            details.append(f"{labels.get(key, key)}由任务输入指定")
        elif (
            isinstance(value, Mapping)
            and value.get("kind") == _SOURCE_FUNCTION_PARAMETER_KIND
        ):
            details.append(f"{labels.get(key, key)}由调用输入指定")
        elif (
            isinstance(value, Mapping)
            and value.get("kind") == _DERIVED_WORKFLOW_VALUE_KIND
        ):
            details.append(f"{labels.get(key, key)}由工作流计算指定")
        elif operator_id == "native:centroids" and key == "ALL_PARTS":
            details.append(
                "ALL_PARTS 为是，为每个部分分别生成质心"
                if value
                else "ALL_PARTS 为否，为每个要素生成单一质心"
            )
        elif operator_id == "native:buffer" and key == "DISSOLVE":
            details.append(
                "DISSOLVE 为是，融合缓冲区"
                if value
                else "DISSOLVE 为否，保留独立缓冲区"
            )
        elif operator_id == "native:dissolve" and key == "FIELD":
            details.append(
                f"按字段 {_display_value(value)} 分组" if value else "不按字段分组"
            )
        elif operator_id in {"native:extractbyextent", "qgis:extractbyextent"} and key == "CLIP":
            details.append(
                "CLIP 为是，裁剪几何" if value else "CLIP 为否，不裁剪几何"
            )
        elif operator_id in {"native:selectbylocation", "qgis:selectbylocation"} and key == "METHOD":
            details.append(f"选择方式为 {_display_value(value)}")
        elif key in labels:
            details.append(f"{labels[key]}为 {_display_value(value)}")
        else:
            details.append(f"{key} 为 {_display_value(value)}")
    return details


def _normalized_operator_ids(record: Mapping[str, Any]) -> list[str]:
    return [str(value).strip().lower() for value in record.get("operator_ids") or []]


def _normalized_edges(record: Mapping[str, Any]) -> list[list[int]]:
    edges: list[list[int]] = []
    for value in record.get("dependency_edges") or []:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
            raise ValueError(f"invalid dependency edge: {value!r}")
        source, target = int(value[0]), int(value[1])
        edges.append([source, target])
    return edges


def _predecessors(edges: Sequence[Sequence[int]], target: int) -> list[int]:
    return [source for source, destination in edges if destination == target]


def _title(operators: Sequence[str], scope: str) -> str:
    titles = [OPERATOR_SEMANTICS[operator_id]["title"] for operator_id in operators]
    base = "并".join(titles) if len(titles) <= 3 else "、".join(titles[:2]) + "等处理"
    return f"局部工作流：{base}" if scope == "local_subworkflow" else base


def _description_clauses(description: str, scope: str) -> list[str]:
    prefix = (
        "在该局部工作流中，"
        if scope == "local_subworkflow"
        else "在该 Processing 工作流中，"
    )
    suffix = "，得到此 Processing 链的结果。"
    if not description.startswith(prefix) or not description.endswith(suffix):
        return []
    body = description[len(prefix) : -len(suffix)]
    return body.split("；随后") if body else []


def build_task_description(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build text only from the frozen Processing DAG, never legacy task text."""

    operators = _normalized_operator_ids(record)
    edges = _normalized_edges(record)
    scope = str(record.get("workflow_unit_scope") or "").strip()
    l3_chain = list(record.get("mapped_l3_chain") or [])
    parameter_facts = _parameter_facts(record, len(operators))
    parameter_resolution = _parameter_resolution(record, len(operators))
    omissions: list[str] = []

    if scope not in ALLOWED_SCOPES:
        omissions.append(f"unsupported_workflow_scope:{scope or 'missing'}")
    if not operators:
        omissions.append("missing_operator_ids")
    missing = [operator_id for operator_id in operators if operator_id not in OPERATOR_SEMANTICS]
    omissions.extend(f"missing_operator_phrase:{operator_id}" for operator_id in missing)
    invalid_edges = [edge for edge in edges if min(edge) < 0 or max(edge) >= len(operators)]
    omissions.extend(f"invalid_dependency_edge:{edge[0]}->{edge[1]}" for edge in invalid_edges)
    for ordinal, resolution in enumerate(parameter_resolution):
        if resolution["status"] == "resolved":
            continue
        reasons = resolution["reasons"] or ["unresolved_parameter_facts"]
        omissions.extend(
            f"parameter_resolution:{ordinal}:{reason}" for reason in reasons
        )

    frozen = {
        "frozen_operator_ids": operators,
        "frozen_dependency_edges": edges,
        "frozen_l3_chain": l3_chain,
        "frozen_parameter_facts": parameter_facts,
        "frozen_parameter_resolution": parameter_resolution,
        "description_policy": DESCRIPTION_POLICY,
    }
    if omissions:
        return {
            **frozen,
            "task_name": "",
            "task_description": "",
            "known_omissions": omissions,
            "description_fidelity_status": "deferred",
            "covered_operator_ids": [],
            "covered_dependency_edges": [],
        }

    clauses: list[str] = []
    for ordinal, operator_id in enumerate(operators):
        semantic = OPERATOR_SEMANTICS[operator_id]
        details = _parameter_details(operator_id, parameter_facts[ordinal])
        action = semantic["action"] + (f"（{'，'.join(details)}）" if details else "")
        predecessors = _predecessors(edges, ordinal)
        if not predecessors:
            clause = f"对输入数据{action}"
        elif len(predecessors) == 1:
            previous_result = OPERATOR_SEMANTICS[operators[predecessors[0]]]["result"]
            clause = f"将前述{previous_result}用于{action}"
        else:
            clause = f"使用前述步骤的处理结果{action}"
        clauses.append(clause)

    scope_prefix = "在该局部工作流中，" if scope == "local_subworkflow" else "在该 Processing 工作流中，"
    description = scope_prefix + "；随后".join(clauses) + "，得到此 Processing 链的结果。"
    return {
        **frozen,
        "task_name": _title(operators, scope),
        "task_description": description,
        "known_omissions": (
            ["outside_explicit_processing_dag_not_described"]
            if scope == "local_subworkflow"
            else []
        ),
        "description_fidelity_status": "candidate",
        "covered_operator_ids": operators,
        "covered_dependency_edges": edges,
    }


def audit_task_description(
    record: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    """Independently verify a deterministic candidate against frozen DAG evidence."""

    operators = _normalized_operator_ids(record)
    edges = _normalized_edges(record)
    scope = str(record.get("workflow_unit_scope") or "").strip()
    description = str(candidate.get("task_description") or "")
    clauses = _description_clauses(description, scope)
    lowered = f" {description.lower()} "
    reasons: list[str] = []

    if candidate.get("description_fidelity_status") != "candidate":
        reasons.append("candidate_not_generated")
    if candidate.get("frozen_operator_ids") != operators:
        reasons.append("operator_chain_mutated")
    if candidate.get("frozen_dependency_edges") != edges:
        reasons.append("dependency_edges_mutated")
    if candidate.get("frozen_l3_chain") != list(record.get("mapped_l3_chain") or []):
        reasons.append("l3_chain_mutated")
    if candidate.get("frozen_parameter_facts") != _parameter_facts(record, len(operators)):
        reasons.append("parameter_facts_mutated")
    if candidate.get("frozen_parameter_resolution") != _parameter_resolution(
        record, len(operators)
    ):
        reasons.append("parameter_resolution_mutated")
    if candidate.get("description_policy") != DESCRIPTION_POLICY:
        reasons.append("unexpected_description_policy")
    if scope not in ALLOWED_SCOPES:
        reasons.append("unsupported_workflow_scope")
    if scope == "local_subworkflow" and "局部工作流" not in description:
        reasons.append("local_scope_not_declared")
    if scope != "local_subworkflow" and "局部工作流" in description:
        reasons.append("unexpected_local_scope_claim")
    if "完整任务" in description:
        reasons.append("overclaims_complete_task")

    for term in FORBIDDEN_LEGACY_TERMS:
        if term in lowered:
            reasons.append(f"forbidden_legacy_term:{term.strip()}")
    if len(clauses) != len(operators):
        reasons.append("description_clause_count_mismatch")
    for ordinal, operator_id in enumerate(operators):
        semantic = OPERATOR_SEMANTICS.get(operator_id)
        if semantic is None:
            reasons.append(f"missing_operator_phrase:{operator_id}")
        elif ordinal >= len(clauses) or semantic["action"] not in clauses[ordinal]:
            reasons.append(f"operator_semantic_not_covered:{operator_id}")
    if candidate.get("covered_operator_ids") != operators:
        reasons.append("operator_coverage_mismatch")
    if candidate.get("covered_dependency_edges") != edges:
        reasons.append("dependency_coverage_mismatch")
    parameter_resolution = _parameter_resolution(record, len(operators))
    for ordinal, resolution in enumerate(parameter_resolution):
        if resolution["status"] == "resolved":
            continue
        resolution_reasons = resolution["reasons"] or ["unresolved_parameter_facts"]
        reasons.extend(
            f"parameter_resolution_deferred:{ordinal}:{reason}"
            for reason in resolution_reasons
        )
    parameter_facts = _parameter_facts(record, len(operators))
    for ordinal, (operator_id, facts) in enumerate(zip(operators, parameter_facts)):
        for key in SAFE_PARAMETER_KEYS.get(operator_id, ()):
            if key not in facts:
                continue
            expected_details = _parameter_details(operator_id, {key: facts[key]})
            if expected_details and not all(
                ordinal < len(clauses) and detail in clauses[ordinal]
                for detail in expected_details
            ):
                reasons.append(
                    f"parameter_value_not_covered:{ordinal}:{operator_id}:{key}"
                )

    return {
        "description_fidelity_passed": not reasons,
        "description_fidelity_reasons": reasons,
        "description_length": len(description),
        "operator_semantic_coverage": len(operators) - sum(
            reason.startswith("operator_semantic_not_covered")
            or reason.startswith("missing_operator_phrase")
            for reason in reasons
        ),
        "operator_count": len(operators),
        "dependency_edge_count": len(edges),
    }
