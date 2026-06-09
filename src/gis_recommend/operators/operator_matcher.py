# -*- coding: utf-8 -*-
"""Case-insensitive operator matcher for GEE→L3 mapping lookups."""


class ImprovedOperatorMatcher:
    """Match operators to L3 mappings with case-insensitive matching."""

    def __init__(self, gee_mapping_metadata):
        self.gee_mapping_metadata = gee_mapping_metadata
        self.lowercase_mapping = {}
        for op, meta in gee_mapping_metadata.items():
            self.lowercase_mapping[op.lower()] = (op, meta)

    def match_operator(self, operator):
        if not operator or not isinstance(operator, str):
            return None
        op_lower = operator.lower().strip()
        if operator in self.gee_mapping_metadata:
            return (operator, self.gee_mapping_metadata[operator])
        if op_lower in self.lowercase_mapping:
            return self.lowercase_mapping[op_lower]
        return None
