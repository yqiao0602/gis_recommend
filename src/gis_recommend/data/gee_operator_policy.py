"""Deterministic policies shared by the legacy GEE cleaning stages."""

_AUXILIARY_VALUE_CONSTRUCTORS = frozenset({
    "ee.Date",
    "ee.List",
    "ee.Number",
})


def is_auxiliary_value_constructor(operator: object) -> bool:
    """Return true only for exact Number/Date/List constructor calls."""
    return isinstance(operator, str) and operator in _AUXILIARY_VALUE_CONSTRUCTORS


def is_filter_predicate_constructor(operator: object) -> bool:
    """Return true for ee.Filter predicate constructors, which are call arguments."""
    return isinstance(operator, str) and operator.lower().startswith("ee.filter.")
