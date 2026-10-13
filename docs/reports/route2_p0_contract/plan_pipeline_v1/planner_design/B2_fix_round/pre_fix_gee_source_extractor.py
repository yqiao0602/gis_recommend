"""Source-grounded GEE call extraction from an ESTree-compatible AST."""

from __future__ import annotations

from typing import Any

from gis_recommend.data.gee_source_evidence import (
    CallEvidence,
    GeeSourceEvidence,
    validate_evidence,
)


EXTRACTOR_VERSION = "gee-source-extractor-v2.3.2"

_ORIGIN_EE = "ee"
_ORIGIN_EE_AUXILIARY = "ee_auxiliary"
_ORIGIN_EXTERNAL = "external"
_ORIGIN_IO = "io"
_ORIGIN_NATIVE = "native"
_ORIGIN_PRESENTATION = "presentation"

_TYPE_CLASSIFIER = "ee.classifier"
_TYPE_ARRAY = "ee.array"
_TYPE_COMPUTED_OBJECT = "ee.computedobject"
_TYPE_DICTIONARY = "ee.dictionary"
_TYPE_FEATURE = "ee.feature"
_TYPE_FEATURECOLLECTION = "ee.featurecollection"
_TYPE_FILTER = "ee.filter"
_TYPE_GEOMETRY = "ee.geometry"
_TYPE_IMAGE = "ee.image"
_TYPE_IMAGECOLLECTION = "ee.imagecollection"
_TYPE_KERNEL = "ee.kernel"
_TYPE_LIST = "ee.list"
_TYPE_NUMBER = "ee.number"
_TYPE_REDUCER = "ee.reducer"
_TYPE_STRING = "ee.string"

_STATIC_EE_TYPES = {
    "ee.array": _TYPE_ARRAY,
    "ee.classifier": _TYPE_CLASSIFIER,
    "ee.dictionary": _TYPE_DICTIONARY,
    "ee.feature": _TYPE_FEATURE,
    "ee.featurecollection": _TYPE_FEATURECOLLECTION,
    "ee.filter": _TYPE_FILTER,
    "ee.geometry": _TYPE_GEOMETRY,
    "ee.image": _TYPE_IMAGE,
    "ee.imagecollection": _TYPE_IMAGECOLLECTION,
    "ee.kernel": _TYPE_KERNEL,
    "ee.list": _TYPE_LIST,
    "ee.number": _TYPE_NUMBER,
    "ee.reducer": _TYPE_REDUCER,
    "ee.string": _TYPE_STRING,
}

_AUXILIARY_EE_TYPES = frozenset(
    {
        _TYPE_ARRAY,
        _TYPE_COMPUTED_OBJECT,
        _TYPE_DICTIONARY,
        _TYPE_LIST,
        _TYPE_NUMBER,
        _TYPE_STRING,
    }
)

_STATIC_FACTORY_RETURN_TYPES = {
    "ee.algorithms.image.segmentation.snic": _TYPE_IMAGE,
    "ee.terrain.aspect": _TYPE_IMAGE,
    "ee.terrain.hillshade": _TYPE_IMAGE,
    "ee.terrain.slope": _TYPE_IMAGE,
}

_SAME_TYPE_METHODS = {
    _TYPE_ARRAY: frozenset({"abs", "add", "divide", "lt", "multiply", "reduce", "subtract"}),
    _TYPE_CLASSIFIER: frozenset({"train"}),
    _TYPE_DICTIONARY: frozenset({"combine", "remove", "set"}),
    _TYPE_FEATURE: frozenset({"centroid", "set", "setgeometry"}),
    _TYPE_FEATURECOLLECTION: frozenset(
        {
            "filter", "filterbounds", "filterdate", "filtermetadata", "flatten", "map", "merge",
            "randomcolumn", "select", "set", "union",
        }
    ),
    _TYPE_FILTER: frozenset({"and", "not", "or"}),
    _TYPE_GEOMETRY: frozenset({"bounds", "buffer", "centroid", "convexhull", "difference", "intersection", "simplify", "union"}),
    _TYPE_IMAGE: frozenset(
        {
            "abs", "acos", "add", "addbands", "and", "arrayslice", "asin", "atan", "atan2",
            "bitwiseand", "byte", "cbrt", "ceil", "clamp", "classify", "clip", "convolve",
            "copyproperties", "cos", "cosh", "divide", "double", "eq", "exp", "expression",
            "float", "floor", "focal_max", "focal_mean", "focal_median", "focal_min", "focal_mode",
            "focalmean", "focalmedian", "focalmode", "glcmtexture", "gt", "gte", "int16", "int32",
            "int64", "int8", "log", "long", "lt", "lte", "mask", "max", "min", "multiply",
            "neq", "normalizeddifference", "not", "or", "pow", "randomvisualizer", "reduce", "remap", "rename",
            "reproject", "resample", "rightshift", "select", "selfmask", "setmulti", "short", "signum",
            "sin", "sinh", "sqrt", "subtract", "tan", "tanh", "toarray", "tobyte", "todouble",
            "tofloat", "toint", "toint16", "toint32", "toint64", "toint8", "tolong", "toshort",
            "touint16", "touint32", "touint8", "uint16", "uint32", "uint8", "unmask", "unmix",
            "updatemask", "unitscale", "where",
        }
    ),
    _TYPE_IMAGECOLLECTION: frozenset(
        {"filter", "filterbounds", "filterdate", "filtermetadata", "map", "merge", "select", "sort"}
    ),
    _TYPE_KERNEL: frozenset({"add", "rotate"}),
    _TYPE_LIST: frozenset({"add", "cat", "distinct", "flatten", "reverse", "slice", "sort", "zip"}),
    _TYPE_NUMBER: frozenset(
        {"abs", "add", "divide", "eq", "gt", "gte", "lt", "lte", "multiply", "neq", "pow", "subtract"}
    ),
    _TYPE_REDUCER: frozenset(
        {"combine", "foreachband", "group", "repeat", "setoutputs", "splitweights", "unweighted", "weighted"}
    ),
    _TYPE_STRING: frozenset({"cat", "replace", "slice"}),
}

_METHOD_RETURN_TYPES = {
    (_TYPE_DICTIONARY, "get"): _TYPE_COMPUTED_OBJECT,
    (_TYPE_DICTIONARY, "keys"): _TYPE_LIST,
    (_TYPE_DICTIONARY, "values"): _TYPE_LIST,
    (_TYPE_FEATURE, "geometry"): _TYPE_GEOMETRY,
    (_TYPE_FEATURE, "get"): _TYPE_COMPUTED_OBJECT,
    (_TYPE_FEATURECOLLECTION, "size"): _TYPE_NUMBER,
    (_TYPE_FEATURECOLLECTION, "first"): _TYPE_FEATURE,
    (_TYPE_FEATURECOLLECTION, "geometry"): _TYPE_GEOMETRY,
    (_TYPE_IMAGE, "sample"): _TYPE_FEATURECOLLECTION,
    (_TYPE_IMAGE, "sampleregions"): _TYPE_FEATURECOLLECTION,
    (_TYPE_IMAGE, "get"): _TYPE_COMPUTED_OBJECT,
    (_TYPE_IMAGE, "reduceregion"): _TYPE_DICTIONARY,
    (_TYPE_IMAGE, "reduceregions"): _TYPE_FEATURECOLLECTION,
    (_TYPE_IMAGECOLLECTION, "reduce"): _TYPE_IMAGE,
    (_TYPE_IMAGECOLLECTION, "size"): _TYPE_NUMBER,
    (_TYPE_LIST, "get"): _TYPE_COMPUTED_OBJECT,
    (_TYPE_STRING, "split"): _TYPE_LIST,
    **{
        (_TYPE_IMAGECOLLECTION, method): _TYPE_IMAGE
        for method in {
            "count", "first", "max", "mean", "median", "min", "mosaic", "qualitymosaic",
            "sum", "toarray", "toarrayperband", "tobands",
        }
    },
}

_EE_AUXILIARY_ROOTS = frozenset({
    "ee.Array",
    "ee.Date",
    "ee.Dictionary",
    "ee.List",
    "ee.Number",
    "ee.String",
})

_CONSTRUCTORS = frozenset({
    "ee.Array",
    "ee.Classifier",
    "ee.Date",
    "ee.Dictionary",
    "ee.Feature",
    "ee.FeatureCollection",
    "ee.Filter",
    "ee.Geometry",
    "ee.Image",
    "ee.ImageCollection",
    "ee.List",
    "ee.Number",
    "ee.Projection",
    "ee.Reducer",
    "ee.String",
})
_CONTROL_METHODS = frozenset({"forEach", "iterate", "map"})
_LOOP_STATEMENTS = frozenset({"DoWhileStatement", "ForInStatement", "ForOfStatement", "ForStatement", "WhileStatement"})
_NATIVE_JS_NAMESPACES = frozenset({
    "Array",
    "ArrayBuffer",
    "BigInt",
    "Boolean",
    "console",
    "DataView",
    "Date",
    "Error",
    "Intl",
    "JSON",
    "Math",
    "Number",
    "Object",
    "Promise",
    "Proxy",
    "Reflect",
    "RegExp",
    "Set",
    "String",
    "Symbol",
    "WeakMap",
    "WeakSet",
})


class _Extractor:
    def __init__(self, *, source_path: str, source_sha256: str):
        self.evidence = GeeSourceEvidence(
            source_path=source_path,
            source_sha256=source_sha256,
            extractor_version=EXTRACTOR_VERSION,
        )
        self.functions: dict[str, dict[str, Any]] = {}
        self.binding_origins: list[dict[str, str]] = [{}]
        self.binding_types: list[dict[str, str]] = [{}]

    def extract(self, ast: dict[str, Any]) -> GeeSourceEvidence:
        if ast.get("type") != "Program" or not isinstance(ast.get("body"), list):
            raise ValueError("AST root must be an ESTree Program with a body")
        self._register_functions(ast["body"])
        for statement in ast["body"]:
            self._visit_statement(statement, scope="program", context="direct", active_helpers=())
        validate_evidence(self.evidence)
        return self.evidence

    def _register_functions(self, statements: list[Any]) -> None:
        for statement in statements:
            if not isinstance(statement, dict) or statement.get("type") != "FunctionDeclaration":
                continue
            identifier = statement.get("id", {})
            name = identifier.get("name") if isinstance(identifier, dict) else None
            if isinstance(name, str) and name:
                self._register_function(name, statement)

    def _register_function(self, name: str, function: dict[str, Any]) -> None:
        if name in self.functions:
            self._flag("duplicate_helper_definition")
        self.functions[name] = function

    def _register_variable_function(self, declaration: dict[str, Any]) -> bool:
        identifier = declaration.get("id")
        init = declaration.get("init")
        if not isinstance(identifier, dict) or identifier.get("type") != "Identifier":
            return False
        name = identifier.get("name")
        if not isinstance(name, str) or not name:
            return False
        if _is_function(init):
            self._register_function(name, init)
            return True
        if not isinstance(init, dict) or init.get("type") != "ObjectExpression":
            return False
        for prop in init.get("properties", []):
            property_name = _static_property_name(prop)
            value = prop.get("value") if isinstance(prop, dict) else None
            if property_name is not None and _is_function(value):
                self._register_function(f"{name}.{property_name}", value)
        return False

    def _flag(self, name: str) -> None:
        if name not in self.evidence.quality_flags:
            self.evidence.quality_flags.append(name)

    def _bind_origin(self, name: str | None, origin: str | None) -> None:
        if name and origin:
            self.binding_origins[-1][name] = origin

    def _lookup_origin(self, name: str | None) -> str | None:
        if not name:
            return None
        for bindings in reversed(self.binding_origins):
            if name in bindings:
                return bindings[name]
        return None

    def _bind_type(self, name: str | None, receiver_type: str | None) -> None:
        if name and receiver_type:
            self.binding_types[-1][name] = receiver_type

    def _lookup_type(self, name: str | None) -> str | None:
        if not name:
            return None
        for bindings in reversed(self.binding_types):
            if name in bindings:
                return bindings[name]
        return None

    def _callee_receiver_origin(self, raw_callee: str | None) -> str | None:
        if not raw_callee or "." not in raw_callee:
            return None
        return self._lookup_origin(raw_callee.split(".", 1)[0])

    def _infer_expression_type(
        self,
        expression: Any,
        *,
        active_helpers: tuple[str, ...] = (),
    ) -> str | None:
        if not isinstance(expression, dict):
            return None
        node_type = expression.get("type")
        if node_type == "Identifier":
            return self._lookup_type(expression.get("name"))
        if node_type == "AssignmentExpression" and expression.get("operator") == "=":
            return self._infer_expression_type(
                expression.get("right"), active_helpers=active_helpers
            )
        if node_type == "SequenceExpression":
            expressions = expression.get("expressions", [])
            if expressions:
                return self._infer_expression_type(
                    expressions[-1], active_helpers=active_helpers
                )
        if node_type not in {"CallExpression", "NewExpression"}:
            if node_type == "MemberExpression":
                static_name = _static_binding_name(expression)
                return _STATIC_EE_TYPES.get(str(static_name or "").lower())
            if node_type in {"ConditionalExpression", "LogicalExpression"}:
                types = {
                    self._infer_expression_type(
                        expression.get(key), active_helpers=active_helpers
                    )
                    for key in ("consequent", "alternate", "left", "right")
                    if expression.get(key) is not None
                }
                types.discard(None)
                if len(types) == 1:
                    return types.pop()
            return None

        callee = expression.get("callee")
        raw_callee = str(_flatten_callee(callee) or "").lower()
        helper_name = _static_binding_name(callee)
        if helper_name in self.functions:
            return self._infer_helper_return_type(
                helper_name,
                self.functions[helper_name],
                expression.get("arguments", []),
                active_helpers=active_helpers,
            )
        if raw_callee == "ee.algorithms.if":
            branch_types = {
                self._infer_expression_type(argument, active_helpers=active_helpers)
                for argument in expression.get("arguments", [])[1:3]
            }
            if len(branch_types) == 1 and None not in branch_types:
                return next(iter(branch_types))
            return None
        if raw_callee in _STATIC_FACTORY_RETURN_TYPES:
            return _STATIC_FACTORY_RETURN_TYPES[raw_callee]
        if raw_callee in _STATIC_EE_TYPES:
            return _STATIC_EE_TYPES[raw_callee]
        if not isinstance(callee, dict) or callee.get("type") != "MemberExpression":
            return None
        object_expression = callee.get("object")
        static_receiver = _STATIC_EE_TYPES.get(
            str(_static_binding_name(object_expression) or "").lower()
        )
        if static_receiver:
            return static_receiver
        receiver_type = self._infer_expression_type(
            object_expression, active_helpers=active_helpers
        )
        method = raw_callee.rsplit(".", 1)[-1]
        if receiver_type and method in _SAME_TYPE_METHODS.get(receiver_type, frozenset()):
            return receiver_type
        return _METHOD_RETURN_TYPES.get((receiver_type, method))

    def _infer_helper_return_type(
        self,
        name: str,
        function: dict[str, Any],
        arguments: list[Any],
        *,
        active_helpers: tuple[str, ...],
    ) -> str | None:
        if name in active_helpers:
            return None
        self.binding_types.append(self._function_argument_types(function, arguments))
        try:
            return_types = self._infer_statement_return_types(
                function.get("body"), active_helpers=(*active_helpers, name)
            )
        finally:
            self.binding_types.pop()
        if len(return_types) != 1 or None in return_types:
            return None
        return next(iter(return_types))

    def _infer_statement_return_types(
        self,
        statement: Any,
        *,
        active_helpers: tuple[str, ...],
    ) -> set[str | None]:
        if not isinstance(statement, dict):
            return set()
        node_type = statement.get("type")
        if node_type != "BlockStatement":
            if node_type == "ReturnStatement":
                return {
                    self._infer_expression_type(
                        statement.get("argument"), active_helpers=active_helpers
                    )
                }
            if node_type in {"ArrowFunctionExpression", "FunctionExpression"}:
                return self._infer_statement_return_types(
                    statement.get("body"), active_helpers=active_helpers
                )
            return {
                self._infer_expression_type(statement, active_helpers=active_helpers)
            }

        return_types: set[str | None] = set()
        for child in statement.get("body", []):
            if not isinstance(child, dict):
                continue
            child_type = child.get("type")
            if child_type == "VariableDeclaration":
                for declaration in child.get("declarations", []):
                    if not isinstance(declaration, dict):
                        continue
                    identifier = declaration.get("id")
                    name = (
                        identifier.get("name")
                        if isinstance(identifier, dict)
                        and identifier.get("type") == "Identifier"
                        else None
                    )
                    self._bind_type(
                        name,
                        self._infer_expression_type(
                            declaration.get("init"), active_helpers=active_helpers
                        ),
                    )
                continue
            if child_type == "ExpressionStatement":
                expression = child.get("expression")
                if (
                    isinstance(expression, dict)
                    and expression.get("type") == "AssignmentExpression"
                    and expression.get("operator") == "="
                ):
                    self._bind_type(
                        _static_binding_name(expression.get("left")),
                        self._infer_expression_type(
                            expression.get("right"), active_helpers=active_helpers
                        ),
                    )
                continue
            if child_type == "ReturnStatement":
                return_types.add(
                    self._infer_expression_type(
                        child.get("argument"), active_helpers=active_helpers
                    )
                )
                break
            if child_type == "IfStatement":
                branch_types: set[str | None] = set()
                for key in ("consequent", "alternate"):
                    branch = child.get(key)
                    if branch is None:
                        branch_types.add(None)
                        continue
                    self.binding_types.append(dict(self.binding_types[-1]))
                    try:
                        branch_types.update(
                            self._infer_statement_return_types(
                                branch, active_helpers=active_helpers
                            )
                        )
                    finally:
                        self.binding_types.pop()
                return_types.update(branch_types or {None})
        return return_types

    def _infer_expression_origin(self, expression: Any) -> str | None:
        if not isinstance(expression, dict):
            return None
        node_type = expression.get("type")
        if node_type == "Identifier":
            return self._lookup_origin(expression.get("name"))
        if node_type in {
            "ArrayExpression",
            "Literal",
            "ObjectExpression",
            "TemplateLiteral",
        }:
            return _ORIGIN_NATIVE
        if node_type in {"CallExpression", "NewExpression"}:
            typed_origin = _origin_for_type(self._infer_expression_type(expression))
            if typed_origin is not None:
                return typed_origin
            raw_callee = _flatten_callee(expression.get("callee"))
            callee = expression.get("callee")
            receiver_origin = (
                self._infer_expression_origin(callee.get("object"))
                if isinstance(callee, dict) and callee.get("type") == "MemberExpression"
                else self._callee_receiver_origin(raw_callee)
            )
            classification, resolution, _ = _classify(
                raw_callee,
                receiver_origin=receiver_origin,
            )
            if raw_callee == "require":
                return _ORIGIN_EXTERNAL
            if raw_callee and raw_callee.startswith("ee."):
                if any(
                    raw_callee == root or raw_callee.startswith(root + ".")
                    for root in _EE_AUXILIARY_ROOTS
                ):
                    return _ORIGIN_EE_AUXILIARY
                return _ORIGIN_EE
            if resolution == "control_container" and receiver_origin:
                return receiver_origin
            if classification == "core" and resolution in {
                "ee_namespace",
                "receiver_ee_binding",
            }:
                return _ORIGIN_EE
            if classification == "presentation":
                return _ORIGIN_PRESENTATION
            if classification == "io":
                return _ORIGIN_IO
            if classification == "support" and resolution in {
                "native_js_namespace",
                "receiver_native_binding",
            }:
                return _ORIGIN_NATIVE
            if classification == "support" and resolution == "receiver_ee_auxiliary_binding":
                return _ORIGIN_EE_AUXILIARY
            return None
        if node_type == "MemberExpression":
            return self._infer_expression_origin(expression.get("object"))
        if node_type in {"ConditionalExpression", "LogicalExpression"}:
            origins = {
                self._infer_expression_origin(expression.get(key))
                for key in ("consequent", "alternate", "left", "right")
                if expression.get(key) is not None
            }
            origins.discard(None)
            if len(origins) == 1:
                return origins.pop()
        return None

    def _function_argument_origins(
        self, function: dict[str, Any], arguments: list[Any]
    ) -> dict[str, str]:
        origins: dict[str, str] = {}
        for parameter, argument in zip(function.get("params", []), arguments):
            if not isinstance(parameter, dict) or parameter.get("type") != "Identifier":
                continue
            name = parameter.get("name")
            origin = self._infer_expression_origin(argument)
            if isinstance(name, str) and origin:
                origins[name] = origin
        return origins

    def _function_argument_types(
        self, function: dict[str, Any], arguments: list[Any]
    ) -> dict[str, str]:
        types: dict[str, str] = {}
        for parameter, argument in zip(function.get("params", []), arguments):
            if not isinstance(parameter, dict) or parameter.get("type") != "Identifier":
                continue
            name = parameter.get("name")
            receiver_type = self._infer_expression_type(argument)
            if isinstance(name, str) and receiver_type:
                types[name] = receiver_type
        return types

    def _callback_parameter_origins(
        self, function: dict[str, Any], raw_callee: str | None
    ) -> dict[str, str]:
        if not raw_callee or raw_callee.rsplit(".", 1)[-1] not in _CONTROL_METHODS:
            return {}
        receiver_origin = self._callee_receiver_origin(raw_callee)
        if raw_callee.startswith("ee."):
            receiver_origin = _ORIGIN_EE
        if receiver_origin == _ORIGIN_EE:
            parameter_origin = _ORIGIN_EE
        elif receiver_origin == _ORIGIN_NATIVE:
            parameter_origin = _ORIGIN_NATIVE
        else:
            return {}
        return {
            parameter["name"]: parameter_origin
            for parameter in function.get("params", [])
            if isinstance(parameter, dict)
            and parameter.get("type") == "Identifier"
            and isinstance(parameter.get("name"), str)
        }

    def _callback_parameter_types(
        self,
        function: dict[str, Any],
        raw_callee: str | None,
        receiver_type: str | None,
    ) -> dict[str, str]:
        if not raw_callee or raw_callee.rsplit(".", 1)[-1] not in _CONTROL_METHODS:
            return {}
        parameter_type = {
            _TYPE_IMAGECOLLECTION: _TYPE_IMAGE,
            _TYPE_FEATURECOLLECTION: _TYPE_FEATURE,
        }.get(receiver_type)
        if parameter_type is None:
            return {}
        return {
            parameter["name"]: parameter_type
            for parameter in function.get("params", [])
            if isinstance(parameter, dict)
            and parameter.get("type") == "Identifier"
            and isinstance(parameter.get("name"), str)
        }

    def _visit_statement(
        self,
        statement: Any,
        *,
        scope: str,
        context: str,
        active_helpers: tuple[str, ...],
    ) -> None:
        if not isinstance(statement, dict):
            return
        node_type = statement.get("type")
        if node_type == "FunctionDeclaration":
            return
        if node_type == "VariableDeclaration":
            for declaration in statement.get("declarations", []):
                if isinstance(declaration, dict):
                    if self._register_variable_function(declaration):
                        continue
                    init = declaration.get("init")
                    self._visit_expression(
                        init, scope=scope, context=context, active_helpers=active_helpers
                    )
                    identifier = declaration.get("id")
                    name = (
                        identifier.get("name")
                        if isinstance(identifier, dict) and identifier.get("type") == "Identifier"
                        else None
                    )
                    self._bind_origin(name, self._infer_expression_origin(init))
                    self._bind_type(name, self._infer_expression_type(init))
            return
        if node_type == "ExpressionStatement":
            self._visit_expression(
                statement.get("expression"), scope=scope, context=context, active_helpers=active_helpers
            )
            return
        if node_type == "ReturnStatement":
            self._visit_expression(
                statement.get("argument"), scope=scope, context=context, active_helpers=active_helpers
            )
            return
        if node_type == "BlockStatement":
            self._register_functions(statement.get("body", []))
            for child in statement.get("body", []):
                self._visit_statement(child, scope=scope, context=context, active_helpers=active_helpers)
            return
        if node_type == "IfStatement":
            self._flag("branch_order_unresolved")
            self._visit_expression(statement.get("test"), scope=scope, context=context, active_helpers=active_helpers)
            self._visit_statement(
                statement.get("consequent"), scope=scope, context=context, active_helpers=active_helpers
            )
            self._visit_statement(
                statement.get("alternate"), scope=scope, context=context, active_helpers=active_helpers
            )
            return
        if node_type in _LOOP_STATEMENTS:
            self._flag("loop_order_unresolved")
            for key in ("init", "left"):
                child = statement.get(key)
                if isinstance(child, dict) and child.get("type", "").endswith("Declaration"):
                    self._visit_statement(child, scope=scope, context=context, active_helpers=active_helpers)
                else:
                    self._visit_expression(child, scope=scope, context=context, active_helpers=active_helpers)
            for key in ("test", "right", "update"):
                self._visit_expression(
                    statement.get(key), scope=scope, context=context, active_helpers=active_helpers
                )
            self._visit_statement(statement.get("body"), scope=scope, context=context, active_helpers=active_helpers)
            return
        if node_type in {"ThrowStatement", "AwaitExpression", "YieldExpression"}:
            self._visit_expression(
                statement.get("argument"), scope=scope, context=context, active_helpers=active_helpers
            )
            return

        for value in statement.values():
            if isinstance(value, dict):
                if value.get("type", "").endswith("Statement"):
                    self._visit_statement(value, scope=scope, context=context, active_helpers=active_helpers)
                else:
                    self._visit_expression(value, scope=scope, context=context, active_helpers=active_helpers)
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, dict):
                        if child.get("type", "").endswith("Statement"):
                            self._visit_statement(child, scope=scope, context=context, active_helpers=active_helpers)
                        else:
                            self._visit_expression(child, scope=scope, context=context, active_helpers=active_helpers)

    def _visit_expression(
        self,
        expression: Any,
        *,
        scope: str,
        context: str,
        active_helpers: tuple[str, ...],
    ) -> None:
        if not isinstance(expression, dict):
            return
        node_type = expression.get("type")
        if node_type == "CallExpression":
            self._visit_call(expression, scope=scope, context=context, active_helpers=active_helpers)
            return
        if node_type == "NewExpression":
            self._visit_new_expression(expression, scope=scope, context=context, active_helpers=active_helpers)
            return
        if node_type == "AssignmentExpression":
            left = expression.get("left")
            right = expression.get("right")
            binding_name = _static_binding_name(left)
            if expression.get("operator") == "=" and binding_name is not None and _is_function(right):
                self._register_function(binding_name, right)
                return
            self._visit_expression(left, scope=scope, context=context, active_helpers=active_helpers)
            self._visit_expression(right, scope=scope, context=context, active_helpers=active_helpers)
            if expression.get("operator") == "=" and binding_name is not None:
                self._bind_origin(binding_name, self._infer_expression_origin(right))
                self._bind_type(binding_name, self._infer_expression_type(right))
            return
        if node_type in {"FunctionExpression", "ArrowFunctionExpression"}:
            return
        if node_type == "MemberExpression":
            self._visit_expression(
                expression.get("object"), scope=scope, context=context, active_helpers=active_helpers
            )
            if expression.get("computed"):
                self._visit_expression(
                    expression.get("property"), scope=scope, context=context, active_helpers=active_helpers
                )
            return
        if node_type in {"ArrayExpression", "SequenceExpression"}:
            key = "elements" if node_type == "ArrayExpression" else "expressions"
            for child in expression.get(key, []):
                self._visit_expression(child, scope=scope, context=context, active_helpers=active_helpers)
            return
        if node_type == "ObjectExpression":
            for prop in expression.get("properties", []):
                if isinstance(prop, dict):
                    self._visit_expression(
                        prop.get("value"), scope=scope, context=context, active_helpers=active_helpers
                    )
            return
        for key in ("argument", "left", "right", "test", "consequent", "alternate", "expression"):
            self._visit_expression(
                expression.get(key), scope=scope, context=context, active_helpers=active_helpers
            )

    def _visit_call(
        self,
        node: dict[str, Any],
        *,
        scope: str,
        context: str,
        active_helpers: tuple[str, ...],
    ) -> None:
        callee = node.get("callee")
        raw_callee = _flatten_callee(callee)
        arguments = node.get("arguments", [])
        receiver_type = (
            self._infer_expression_type(callee.get("object"))
            if isinstance(callee, dict) and callee.get("type") == "MemberExpression"
            else None
        )

        if isinstance(callee, dict) and callee.get("type") == "MemberExpression":
            self._visit_expression(
                callee.get("object"), scope=scope, context=context, active_helpers=active_helpers
            )

        for argument in arguments:
            if not _is_function(argument):
                self._visit_expression(argument, scope=scope, context=context, active_helpers=active_helpers)

        if raw_callee in self.functions:
            if raw_callee in active_helpers:
                self._flag("recursive_helper")
                self._emit(
                    node,
                    raw_callee=raw_callee,
                    classification="unresolved",
                    resolution="recursive_helper",
                    scope=scope,
                    context=context,
                    receiver_type=None,
                    flags=("recursive_helper",),
                )
                return
            helper = self.functions[raw_callee]
            self.binding_origins.append(self._function_argument_origins(helper, arguments))
            self.binding_types.append(self._function_argument_types(helper, arguments))
            try:
                self._visit_function_body(
                    helper,
                    scope=raw_callee,
                    context="helper_inline",
                    active_helpers=(*active_helpers, raw_callee),
                )
            finally:
                self.binding_types.pop()
                self.binding_origins.pop()
            return

        classification, resolution, flags = _classify(
            raw_callee,
            receiver_origin=(
                self._infer_expression_origin(callee.get("object"))
                if isinstance(callee, dict) and callee.get("type") == "MemberExpression"
                else self._callee_receiver_origin(raw_callee)
            ),
        )
        method = str(raw_callee or "").rsplit(".", 1)[-1].casefold()
        if method == "filter" and arguments:
            predicate = arguments[0]
            predicate_callee = (
                _flatten_callee(predicate.get("callee"))
                if isinstance(predicate, dict)
                and predicate.get("type") == "CallExpression"
                else None
            )
            if predicate_callee and predicate_callee.casefold().startswith("ee.filter."):
                predicate_method = predicate_callee.rsplit(".", 1)[-1].casefold()
                flags = (*flags, f"filter_predicate:{predicate_method}")
        if (
            receiver_type == "ee.imagecollection"
            and method == "merge"
            and arguments
        ):
            argument_type = self._infer_expression_type(arguments[0])
            if argument_type is not None and argument_type != "ee.imagecollection":
                flags = (*flags, "imagecollection_merge_argument_type_mismatch")
        self._emit(
            node,
            raw_callee=raw_callee,
            classification=classification,
            resolution=resolution,
            scope=scope,
            context=context,
            receiver_type=receiver_type,
            flags=flags,
        )

        for argument in arguments:
            if _is_function(argument):
                self._flag("callback")
                callback_type = (
                    "arrow_callback"
                    if argument.get("type") == "ArrowFunctionExpression"
                    else "function_callback"
                )
                self._flag(callback_type)
                body = argument.get("body")
                callback_scope = f"{scope}:callback"
                self.binding_origins.append(
                    self._callback_parameter_origins(argument, raw_callee)
                )
                self.binding_types.append(
                    self._callback_parameter_types(argument, raw_callee, receiver_type)
                )
                try:
                    if isinstance(body, dict) and body.get("type") == "BlockStatement":
                        self._visit_statement(
                            body,
                            scope=callback_scope,
                            context="callback",
                            active_helpers=active_helpers,
                        )
                    else:
                        self._visit_expression(
                            body,
                            scope=callback_scope,
                            context="callback",
                            active_helpers=active_helpers,
                        )
                finally:
                    self.binding_types.pop()
                    self.binding_origins.pop()
            else:
                helper_name = _static_binding_name(argument)
                if (
                    helper_name not in self.functions
                    or raw_callee is None
                    or raw_callee.rsplit(".", 1)[-1] not in _CONTROL_METHODS
                ):
                    continue
                self._flag("callback")
                self._flag("function_callback")
                self._flag("named_callback")
                if helper_name in active_helpers:
                    self._flag("recursive_helper")
                    self._emit(
                        node,
                        raw_callee=helper_name,
                        classification="unresolved",
                        resolution="recursive_helper",
                        scope=scope,
                        context="callback",
                        receiver_type=None,
                        flags=("recursive_helper",),
                    )
                    continue
                helper = self.functions[helper_name]
                self.binding_origins.append(
                    self._callback_parameter_origins(helper, raw_callee)
                )
                self.binding_types.append(
                    self._callback_parameter_types(helper, raw_callee, receiver_type)
                )
                try:
                    self._visit_function_body(
                        helper,
                        scope=helper_name,
                        context="callback",
                        active_helpers=(*active_helpers, helper_name),
                    )
                finally:
                    self.binding_types.pop()
                    self.binding_origins.pop()

    def _visit_new_expression(
        self,
        node: dict[str, Any],
        *,
        scope: str,
        context: str,
        active_helpers: tuple[str, ...],
    ) -> None:
        callee = node.get("callee")
        if isinstance(callee, dict) and callee.get("type") == "MemberExpression":
            self._visit_expression(
                callee.get("object"), scope=scope, context=context, active_helpers=active_helpers
            )
        arguments = node.get("arguments", [])
        for argument in arguments:
            if not _is_function(argument):
                self._visit_expression(argument, scope=scope, context=context, active_helpers=active_helpers)
        raw_callee = _flatten_callee(callee)
        receiver_type = (
            self._infer_expression_type(callee.get("object"))
            if isinstance(callee, dict) and callee.get("type") == "MemberExpression"
            else None
        )
        classification, resolution, flags = _classify(
            raw_callee,
            receiver_origin=(
                self._infer_expression_origin(callee.get("object"))
                if isinstance(callee, dict) and callee.get("type") == "MemberExpression"
                else self._callee_receiver_origin(raw_callee)
            ),
        )
        self._emit(
            node,
            raw_callee=raw_callee,
            classification=classification,
            resolution=resolution,
            scope=scope,
            context=context,
            receiver_type=receiver_type,
            flags=flags,
        )

    def _visit_function_body(
        self,
        function: dict[str, Any],
        *,
        scope: str,
        context: str,
        active_helpers: tuple[str, ...],
    ) -> None:
        body = function.get("body")
        if isinstance(body, dict) and body.get("type") == "BlockStatement":
            self._visit_statement(body, scope=scope, context=context, active_helpers=active_helpers)
            return
        self._visit_expression(body, scope=scope, context=context, active_helpers=active_helpers)

    def _emit(
        self,
        node: dict[str, Any],
        *,
        raw_callee: str | None,
        classification: str,
        resolution: str,
        scope: str,
        context: str,
        receiver_type: str | None,
        flags: tuple[str, ...],
    ) -> None:
        ordinal = len(self.evidence.ordered_calls)
        location = _source_location(node)
        call_flags = list(flags)
        if location is None:
            call_flags.append("missing_source_location")
            self._flag("missing_source_location")
        for flag in flags:
            self._flag(flag)
        call = CallEvidence(
            ordinal=ordinal,
            raw_callee=raw_callee,
            classification=classification,
            resolution=resolution,
            scope=scope,
            context=context,
            receiver_type=receiver_type,
            source_location=location,
            flags=tuple(call_flags),
        )
        self.evidence.ordered_calls.append(call)
        layer = {
            "core": self.evidence.core_operator_chain,
            "io": self.evidence.io_contract,
            "presentation": self.evidence.presentation_actions,
            "support": self.evidence.support_calls,
            "unresolved": self.evidence.unresolved_calls,
        }[classification]
        layer.append(ordinal)


def _is_function(node: Any) -> bool:
    return isinstance(node, dict) and node.get("type") in {"ArrowFunctionExpression", "FunctionExpression"}


def _static_property_name(prop: Any) -> str | None:
    if not isinstance(prop, dict) or prop.get("computed"):
        return None
    key = prop.get("key")
    if not isinstance(key, dict):
        return None
    if key.get("type") == "Identifier":
        name = key.get("name")
    elif key.get("type") == "Literal":
        name = key.get("value")
    else:
        return None
    return name if isinstance(name, str) and name else None


def _static_binding_name(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("type") == "Identifier":
        name = node.get("name")
        return name if isinstance(name, str) and name else None
    if node.get("type") != "MemberExpression" or node.get("computed"):
        return None
    root = _static_binding_name(node.get("object"))
    prop = node.get("property")
    name = prop.get("name") if isinstance(prop, dict) and prop.get("type") == "Identifier" else None
    if root is None or not isinstance(name, str) or not name:
        return None
    return f"{root}.{name}"


def _flatten_callee(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    node_type = node.get("type")
    if node_type == "Identifier":
        return node.get("name")
    if node_type == "NewExpression":
        return _flatten_callee(node.get("callee"))
    if node_type == "CallExpression":
        return _flatten_callee(node.get("callee"))
    if node_type != "MemberExpression" or node.get("computed"):
        return None
    root = _flatten_callee(node.get("object"))
    prop = node.get("property", {})
    name = prop.get("name") if isinstance(prop, dict) and prop.get("type") == "Identifier" else None
    if not root or not name:
        return None
    return f"{root}.{name}"


def _origin_for_type(receiver_type: str | None) -> str | None:
    if receiver_type in _AUXILIARY_EE_TYPES:
        return _ORIGIN_EE_AUXILIARY
    if receiver_type in _STATIC_EE_TYPES.values():
        return _ORIGIN_EE
    return None


def _classify(
    raw_callee: str | None, *, receiver_origin: str | None = None
) -> tuple[str, str, tuple[str, ...]]:
    if raw_callee is None:
        return "unresolved", "dynamic_callee", ("dynamic_callee",)
    if raw_callee == "require":
        return "support", "external_module_loader", ()
    if raw_callee == "print" or raw_callee.startswith(("Map.", "ui.", "Chart.")):
        return "presentation", "exact_prefix", ()
    if raw_callee.startswith("Export."):
        return "io", "exact_prefix", ()
    root = raw_callee.split(".", 1)[0]
    if root in _NATIVE_JS_NAMESPACES:
        return "support", "native_js_namespace", ("native_js_call",)
    if raw_callee in _CONSTRUCTORS:
        return "support", "exact_constructor", ()
    if "." in raw_callee and receiver_origin == _ORIGIN_EE_AUXILIARY:
        return "support", "receiver_ee_auxiliary_binding", ()
    if "." in raw_callee and receiver_origin == _ORIGIN_EXTERNAL:
        return "unresolved", "receiver_external_module", ("external_module_call",)
    method = raw_callee.rsplit(".", 1)[-1]
    if method in _CONTROL_METHODS:
        return "support", "control_container", ()
    if raw_callee.startswith("ee."):
        return "core", "ee_namespace", ()
    if "." in raw_callee:
        if receiver_origin == _ORIGIN_PRESENTATION:
            return "presentation", "receiver_presentation_binding", ()
        if receiver_origin == _ORIGIN_IO:
            return "io", "receiver_io_binding", ()
        if receiver_origin == _ORIGIN_NATIVE:
            return "support", "receiver_native_binding", ("native_js_call",)
        if receiver_origin == _ORIGIN_EE_AUXILIARY:
            return "support", "receiver_ee_auxiliary_binding", ()
        if receiver_origin == _ORIGIN_EE:
            return "core", "receiver_ee_binding", ()
        return "core", "receiver_untyped", ("untyped_receiver",)
    return "unresolved", "unbound_identifier", ("unbound_identifier",)


def _source_location(node: dict[str, Any]) -> dict[str, int] | None:
    location = node.get("loc")
    if not isinstance(location, dict):
        return None
    start = location.get("start")
    end = location.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None
    values = (start.get("line"), start.get("column"), end.get("line"), end.get("column"))
    if not all(isinstance(value, int) for value in values):
        return None
    return {
        "start_line": values[0],
        "start_column": values[1],
        "end_line": values[2],
        "end_column": values[3],
    }


def extract_gee_source_evidence(
    ast: dict[str, Any],
    *,
    source_path: str,
    source_sha256: str,
) -> GeeSourceEvidence:
    """Extract ordered call evidence without normalizing names or mapping taxonomy."""

    return _Extractor(source_path=source_path, source_sha256=source_sha256).extract(ast)
