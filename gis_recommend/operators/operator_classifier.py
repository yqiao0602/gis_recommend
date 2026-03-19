"""
Operator Classifier - Classify GEE operators into categories

Categories:
- infrastructure: Data structure constructors (ee.ImageCollection, ee.Image, etc.)
- user_variable: User-defined variables and UI operations
- orphan_gis: GIS operators without L3 mappings
- gis_operator: Valid GIS operators
"""


class OperatorClassifier:
    """Classify operators into categories"""

    # Infrastructure keywords (data structures, not GIS operations)
    INFRASTRUCTURE_KEYWORDS = [
        'ee.imagecollection',
        'ee.image',
        'ee.featurecollection',
        'ee.feature',
        'ee.geometry',
        'ee.date',
        'ee.list',
        'ee.dictionary',
        'ee.number',
        'ee.string',
        'ee.array',
    ]

    # UI and user variable patterns
    UI_KEYWORDS = [
        'map.',
        'print',
        'chart.',
        'export.',
        'ui.',
    ]

    def __init__(self):
        pass

    def classify_operator(self, operator):
        """
        Classify an operator

        Args:
            operator: Operator name (e.g., "ee.image.select")

        Returns:
            Tuple of (category, corrected_operator, reason)
            - category: 'infrastructure', 'user_variable', 'gis_operator'
            - corrected_operator: Same as input (no correction needed for our standardized data)
            - reason: Classification reason
        """
        if not operator or not isinstance(operator, str):
            return 'user_variable', operator, 'Empty or invalid operator'

        op_lower = operator.lower().strip()

        # Check if it's infrastructure (pure data structure)
        for infra in self.INFRASTRUCTURE_KEYWORDS:
            if op_lower == infra:  # Exact match only
                return 'infrastructure', operator, f'Infrastructure: {infra}'

        # Check if it's UI or user variable
        for ui in self.UI_KEYWORDS:
            if op_lower.startswith(ui):
                return 'user_variable', operator, f'UI operation: {ui}'

        # Check for user-defined variables (no 'ee.' prefix)
        if not op_lower.startswith('ee.'):
            # Special cases: flatten, Map.addLayer, etc. are valid operations
            if op_lower in ['flatten', 'map.addlayer', 'map.centerobject']:
                return 'gis_operator', operator, 'Valid non-GEE operation'
            return 'user_variable', operator, 'User-defined variable'

        # Otherwise, it's a GIS operator
        return 'gis_operator', operator, 'Valid GIS operator'
