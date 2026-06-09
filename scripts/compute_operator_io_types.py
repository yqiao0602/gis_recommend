"""
compute_operator_io_types.py

Pre-compute normalized I/O data types for all QGIS operators from Neo4j.
Output: outputs/qgis_operator_io_types.json
"""

import json
from pathlib import Path
from neo4j import GraphDatabase

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "qgis_operator_io_types.json"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "12345678")

# Normalize fine-grained types to coarse categories
TYPE_NORMALIZATION = {
    "polygon": "vector", "point": "vector", "line": "vector",
    "multipolygon": "vector", "multipoint": "vector", "multiline": "vector",
    "table": "vector", "features": "vector",
    "raster": "raster", "grid": "raster", "dem": "raster",
}

# Types that expand to multiple categories (generic spatial types)
TYPE_EXPANSION = {
    "geographicData": ["vector", "raster"],
}

# Non-spatial types to exclude
EXCLUDED_TYPES = {"LiteralData"}


def normalize_types(raw_list: list) -> list:
    """Normalize a list of raw DataType names to coarse categories."""
    result = set()
    for raw in raw_list:
        if not raw or raw in EXCLUDED_TYPES:
            continue
        if raw in TYPE_EXPANSION:
            result.update(TYPE_EXPANSION[raw])
        elif raw in TYPE_NORMALIZATION:
            result.add(TYPE_NORMALIZATION[raw])
        else:
            result.add(raw)
    return sorted(result)


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    # Query all QGIS operators
    with driver.session() as session:
        ops = session.run("MATCH (q:QGIS_Operator) RETURN q.name AS name").data()
    op_names = [r["name"] for r in ops]
    print(f"[OK] Found {len(op_names)} QGIS operators")

    operators = {}
    no_io_count = 0

    with driver.session() as session:
        for name in op_names:
            # Query inputs (required only)
            input_result = session.run("""
                MATCH (q:QGIS_Operator {name: $name})-[:hasInput]->(i:Input)
                OPTIONAL MATCH (i)-[:links_to]->(dt:DataType)
                WHERE i.optional IS NULL OR i.optional = false
                RETURN collect(DISTINCT dt.name) AS data_types
            """, name=name).single()

            # Query outputs
            output_result = session.run("""
                MATCH (q:QGIS_Operator {name: $name})-[:hasOutput]->(o:Output)
                OPTIONAL MATCH (o)-[:links_to]->(dt:DataType)
                RETURN collect(DISTINCT dt.name) AS data_types
            """, name=name).single()

            raw_inputs = input_result["data_types"] if input_result else []
            raw_outputs = output_result["data_types"] if output_result else []

            # Normalize and deduplicate
            norm_inputs = normalize_types(raw_inputs)
            norm_outputs = normalize_types(raw_outputs)

            if norm_inputs or norm_outputs:
                operators[name] = {
                    "inputs": norm_inputs,
                    "outputs": norm_outputs,
                }
            else:
                no_io_count += 1

    driver.close()

    output = {
        "version": "1.0",
        "operator_count": len(operators),
        "no_io_count": no_io_count,
        "operators": operators,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Stats
    raster_only = sum(1 for v in operators.values()
                      if v["inputs"] == ["raster"] or v["outputs"] == ["raster"])
    vector_only = sum(1 for v in operators.values()
                      if v["inputs"] == ["vector"] or v["outputs"] == ["vector"])
    print(f"[DONE] Saved {len(operators)} operators to {OUTPUT_PATH}")
    print(f"  No I/O info: {no_io_count}")
    print(f"  Raster-only (input or output): {raster_only}")
    print(f"  Vector-only (input or output): {vector_only}")
    for name in ["Slope", "Buffer vectors", "Warp", "Raster Calculator", "Merge vector layers"]:
        if name in operators:
            print(f"  {name}: in={operators[name]['inputs']}, out={operators[name]['outputs']}")


if __name__ == "__main__":
    main()
