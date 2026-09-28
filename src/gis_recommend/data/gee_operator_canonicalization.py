"""Stable GEE operator canonicalization primitives shared by data builders."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class MappingEntry:
    canonical_operator: str
    primary_l3: str
    mapping_confidence: float | None
    has_ambiguity: bool


@dataclass(frozen=True)
class OperatorCanonicalization:
    canonical_operator_sequence: list[str]
    l3_sequence: list[str]
    skipped_raw_operators: list[str]
    unmapped_raw_operators: list[str]
    canonical_unmapped_l3_operators: list[str]
    used_old_l3_sequence: bool = False


IMAGE_METHODS = frozenset(
    {
        "abs",
        "add",
        "addbands",
        "and",
        "arrayslice",
        "bitwiseand",
        "classify",
        "clip",
        "copyproperties",
        "divide",
        "eq",
        "expression",
        "glcmtexture",
        "gt",
        "gte",
        "lt",
        "lte",
        "log",
        "mask",
        "max",
        "min",
        "multiply",
        "neq",
        "normalizeddifference",
        "not",
        "or",
        "pixelarea",
        "pow",
        "reduce",
        "reduceregion",
        "reduceregions",
        "rename",
        "reproject",
        "rightshift",
        "sample",
        "sampleregions",
        "select",
        "selfmask",
        "subtract",
        "toarray",
        "tofloat",
        "toint",
        "unmask",
        "updatemask",
        "unitscale",
        "where",
    }
)
IMAGECOLLECTION_METHODS = frozenset(
    {
        "count",
        "filter",
        "filterbounds",
        "filterdate",
        "filtermetadata",
        "first",
        "map",
        "max",
        "mean",
        "median",
        "merge",
        "min",
        "mosaic",
        "qualitymosaic",
        "select",
        "sum",
        "toarray",
        "toarrayperband",
        "tobands",
    }
)
FEATURE_METHODS = frozenset({"centroid", "get", "set"})
FEATURECOLLECTION_METHODS = frozenset(
    {
        "filter",
        "filterbounds",
        "flatten",
        "geometry",
        "merge",
        "randomcolumn",
        "select",
        "set",
        "union",
    }
)
FILTER_METHODS = frozenset(
    {
        "and",
        "calendarrange",
        "date",
        "eq",
        "gt",
        "inlist",
        "listcontains",
        "lt",
        "maxdifference",
        "not",
        "or",
    }
)
REDUCER_METHODS = frozenset({"count", "first", "max", "mean", "median", "min", "sum"})
CLASSIFIER_METHODS = frozenset({"confusionmatrix", "smilerandomforest", "train"})
GEOMETRY_METHODS = frozenset({"coveringgrid"})

SUPPORT_METHODS = frozenset(
    {
        "advance",
        "bandnames",
        "bandtypes",
        "cat",
        "date",
        "difference",
        "evaluate",
        "format",
        "fromimages",
        "getinfo",
        "getrelative",
        "imnormalize",
        "loadgeotiff",
        "int",
        "addall",
        "arraylength",
        "millis",
        "maxdifference",
        "objecttype",
        "palette",
        "parse",
        "propertynames",
        "remove",
        "size",
        "style",
        "toint32",
        "visualize",
        "copyproperties",
        "getvideothumburl",
        "id",
        "keys",
        "setdefaultworkloadtag",
        "setoutputs",
        "sort",
        "toarrayperband",
        "toimage",
        "values",
    }
)
SUPPORT_ROOTS = frozenset(
    {
        "ee.data",
        "ee.date",
        "ee.dictionary",
        "ee.geometry",
        "ee.kernel",
        "ee.list",
        "ee.number",
        "ee.string",
        "ee.algorithms.if",
    }
)


def load_gee_l3_mapping(path: Path) -> dict[str, MappingEntry]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    gee_to_l3 = payload.get("mapping_metadata", {}).get("gee_to_l3", {})
    if not isinstance(gee_to_l3, dict) or not gee_to_l3:
        raise ValueError(f"{path} does not contain mapping_metadata.gee_to_l3")

    entries: dict[str, MappingEntry] = {}
    exact_lower_keys = {
        str(operator).strip().lower()
        for operator in gee_to_l3
        if str(operator).strip() == str(operator).strip().lower()
    }
    for operator, meta in gee_to_l3.items():
        if not isinstance(meta, dict):
            continue
        primary_l3 = str(meta.get("primary_l3") or "").strip()
        if not primary_l3 or not primary_l3.startswith("L3_"):
            continue
        normalized = str(operator).strip().lower()
        if not normalized:
            continue
        if normalized in entries and normalized in exact_lower_keys and str(operator).strip() != normalized:
            continue
        confidence = meta.get("mapping_confidence")
        entries[normalized] = MappingEntry(
            canonical_operator=normalized,
            primary_l3=primary_l3,
            mapping_confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            has_ambiguity=bool(meta.get("has_ambiguity")),
        )
    if not entries:
        raise ValueError(f"{path} contains no usable GEE->L3 entries")
    return entries


def load_gee_operator_catalog(path: Path) -> frozenset[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_catalog = payload.get("gee_op", {})
    if not isinstance(raw_catalog, dict) or not raw_catalog:
        raise ValueError(f"{path} does not contain gee_op")
    catalog = frozenset(
        str(operator).strip().lower()
        for operator in raw_catalog
        if str(operator).strip().lower().startswith(("ee.", "export."))
    )
    if not catalog:
        raise ValueError(f"{path} contains no canonical GEE operators")
    return catalog


def load_gee_skip_operators(path: Path) -> frozenset[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_operators = payload.get("skip_operators")
    if not isinstance(raw_operators, list) or not raw_operators:
        raise ValueError(f"{path} does not contain skip_operators")
    operators = frozenset(
        str(operator).strip().lower()
        for operator in raw_operators
        if isinstance(operator, str) and operator.strip()
    )
    if len(operators) != len(raw_operators):
        raise ValueError(f"{path} contains invalid or duplicate skip operators")
    return operators


def _method(raw_operator: str) -> str:
    return raw_operator.rsplit(".", 1)[-1].lower()


def _has_prefix(raw_operator: str, prefix: str) -> bool:
    return raw_operator == prefix or raw_operator.startswith(prefix + ".")


def _is_support_call(raw_operator: str) -> bool:
    if raw_operator.startswith(("map.", "ui.", "chart.", "export.")):
        return True
    if any(_has_prefix(raw_operator, root) for root in SUPPORT_ROOTS):
        return True
    return _method(raw_operator) in SUPPORT_METHODS


def _candidate_keys(
    raw_operator: str,
    *,
    receiver_type: str | None = None,
    allow_family_heuristics: bool = True,
) -> list[str]:
    method = _method(raw_operator)
    normalized_receiver_type = str(receiver_type or "").strip().lower()
    candidates: list[str] = []
    if normalized_receiver_type.startswith("ee."):
        candidates.append(f"{normalized_receiver_type}.{method}")
    candidates.append(raw_operator)

    if raw_operator.endswith(".apply") and "join" in raw_operator:
        candidates.append("ee.join.saveall")
    if "errormatrix" in raw_operator:
        candidates.append("ee.featurecollection.errormatrix")
    if method in {"accuracy", "consumersaccuracy", "producersaccuracy"}:
        candidates.append(f"ee.confusionmatrix.{method}")

    if raw_operator.startswith("ee.filter."):
        candidates.append(f"ee.filter.{method}")
    elif raw_operator.startswith("ee.reducer."):
        candidates.append(f"ee.reducer.{method}")
    elif raw_operator.startswith("ee.classifier."):
        candidates.append(f"ee.classifier.{method}")
        if method == "train":
            candidates.append("ee.classifier.train")
    elif raw_operator.startswith("ee.imagecollection."):
        candidates.append(f"ee.imagecollection.{method}")
    elif raw_operator.startswith("ee.image."):
        candidates.append(f"ee.image.{method}")
    elif raw_operator.startswith("ee.featurecollection."):
        candidates.append(f"ee.featurecollection.{method}")
    elif raw_operator.startswith("ee.feature."):
        candidates.append(f"ee.feature.{method}")

    if allow_family_heuristics:
        if method in IMAGECOLLECTION_METHODS:
            candidates.append(f"ee.imagecollection.{method}")
        if method in FEATURECOLLECTION_METHODS:
            candidates.append(f"ee.featurecollection.{method}")
        if method in FEATURE_METHODS:
            candidates.append(f"ee.feature.{method}")
        if method in IMAGE_METHODS:
            candidates.append(f"ee.image.{method}")
        if method in FILTER_METHODS:
            candidates.append(f"ee.filter.{method}")
        if method in REDUCER_METHODS:
            candidates.append(f"ee.reducer.{method}")
        if method in CLASSIFIER_METHODS:
            candidates.append(f"ee.classifier.{method}")
        if method in GEOMETRY_METHODS:
            candidates.append(f"ee.geometry.point.{method}")

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _mapping_for_operator(
    raw_operator: str,
    mapping: dict[str, MappingEntry],
    *,
    receiver_type: str | None = None,
    allow_family_heuristics: bool = True,
) -> MappingEntry | None:
    for candidate in _candidate_keys(
        raw_operator,
        receiver_type=receiver_type,
        allow_family_heuristics=allow_family_heuristics,
    ):
        if candidate in mapping:
            return mapping[candidate]
    return None


def matches_skip_authority(
    raw_operator: str,
    skip_operators: frozenset[str],
    *,
    receiver_type: str | None = None,
    allow_family_heuristics: bool = False,
) -> bool:
    return any(
        candidate in skip_operators
        for candidate in _candidate_keys(
            raw_operator.strip().lower(),
            receiver_type=receiver_type,
            allow_family_heuristics=allow_family_heuristics,
        )
    )


def _unique_mapping_for_method(
    raw_operator: str,
    mapping: dict[str, MappingEntry],
    operator_catalog: frozenset[str] | None,
) -> MappingEntry | None:
    suffix = "." + _method(raw_operator)
    matches = {
        entry.canonical_operator: entry
        for key, entry in mapping.items()
        if key.endswith(suffix)
    }
    if len(matches) != 1:
        return None
    entry = next(iter(matches.values()))
    if operator_catalog is not None:
        catalog_matches = {operator for operator in operator_catalog if operator.endswith(suffix)}
        if catalog_matches != {entry.canonical_operator}:
            return None
    return entry


def _catalog_operator_for_raw(
    raw_operator: str,
    operator_catalog: frozenset[str],
    *,
    receiver_is_proven_ee: bool,
    receiver_type: str | None = None,
) -> str | None:
    if raw_operator in operator_catalog:
        return raw_operator
    if not receiver_is_proven_ee:
        return None
    suffix = "." + _method(raw_operator)
    typed_candidate = f"{str(receiver_type or '').strip().lower()}{suffix}"
    if receiver_type and typed_candidate in operator_catalog:
        return typed_candidate
    matches = [operator for operator in operator_catalog if operator.endswith(suffix)]
    return matches[0] if len(matches) == 1 else None


def canonicalize_operator_sequence(
    raw_operator_sequence: list[str],
    mapping: dict[str, MappingEntry],
    *,
    proven_ee_receivers: list[bool] | None = None,
    receiver_types: list[str | None] | None = None,
    operator_catalog: frozenset[str] | None = None,
    skip_operators: frozenset[str] | None = None,
) -> OperatorCanonicalization:
    if proven_ee_receivers is not None and len(proven_ee_receivers) != len(raw_operator_sequence):
        raise ValueError("proven_ee_receivers must align with raw_operator_sequence")
    if receiver_types is not None and len(receiver_types) != len(raw_operator_sequence):
        raise ValueError("receiver_types must align with raw_operator_sequence")
    canonical_ops: list[str] = []
    l3_sequence: list[str] = []
    skipped: list[str] = []
    unmapped: list[str] = []
    canonical_unmapped_l3: list[str] = []
    for index, raw_operator in enumerate(raw_operator_sequence):
        if not isinstance(raw_operator, str) or not raw_operator.strip():
            continue
        raw_stripped = raw_operator.strip()
        raw_normalized = raw_stripped.lower()
        receiver_type = receiver_types[index] if receiver_types is not None else None
        normalized_skip = skip_operators or frozenset()
        if matches_skip_authority(
            raw_normalized,
            normalized_skip,
            receiver_type=receiver_type,
            allow_family_heuristics=receiver_types is None,
        ):
            skipped.append(raw_stripped)
            continue
        mapped = _mapping_for_operator(
            raw_normalized,
            mapping,
            receiver_type=receiver_type,
            allow_family_heuristics=receiver_types is None,
        )
        receiver_is_proven_ee = bool(
            proven_ee_receivers is not None and proven_ee_receivers[index]
        )
        if mapped is None and receiver_is_proven_ee:
            mapped = _unique_mapping_for_method(raw_normalized, mapping, operator_catalog)
        if mapped is not None:
            canonical_ops.append(mapped.canonical_operator)
            l3_sequence.append(mapped.primary_l3)
            continue
        if _is_support_call(raw_normalized):
            skipped.append(raw_stripped)
            continue
        if operator_catalog:
            catalog_operator = _catalog_operator_for_raw(
                raw_normalized,
                operator_catalog,
                receiver_is_proven_ee=receiver_is_proven_ee,
                receiver_type=receiver_type,
            )
            if catalog_operator is not None:
                canonical_unmapped_l3.append(catalog_operator)
                continue
        unmapped.append(raw_stripped)
    return OperatorCanonicalization(
        canonical_operator_sequence=canonical_ops,
        l3_sequence=l3_sequence,
        skipped_raw_operators=skipped,
        unmapped_raw_operators=unmapped,
        canonical_unmapped_l3_operators=canonical_unmapped_l3,
    )
