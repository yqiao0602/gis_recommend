"""
compute_semantic_scores.py

离线预计算 L3→QGIS 语义相似度

1. 从 Neo4j 读取所有 L3 描述（350条）和 QGIS 描述（1291条）
2. 用 all-MiniLM-L6-v2 编码所有文本
3. 对每条 maps_to_l3 关系计算 cosine similarity
4. 对没有映射的 L3，找 Top-5 最相似的 QGIS 算子（补全缺失映射）
5. 输出 outputs/l3_qgis_semantic_scores.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

# ── 项目路径 ──────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "l3_qgis_semantic_scores.json"

# ── Neo4j 连接 ───────────────────────────────────────────────
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "12345678"


def connect_neo4j():
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    with driver.session() as s:
        s.run("RETURN 1").single()
    print("[OK] Neo4j connected")
    return driver


def fetch_l3_descriptions(driver) -> dict:
    """返回 {l3_code: {"name": ..., "description": ...}}"""
    with driver.session() as s:
        records = s.run("""
            MATCH (l:L3_Primitive)
            RETURN l.code AS code, l.name AS name,
                   l.description AS description
        """)
        result = {}
        for r in records:
            code = r["code"]
            name = r["name"] or ""
            desc = r["description"] or ""
            result[code] = {"name": name, "description": desc}
    print(f"[OK] Loaded {len(result)} L3 primitives")
    return result


def fetch_qgis_descriptions(driver) -> dict:
    """返回 {qgis_name: {"description": ..., "algorithm_id": ...}}"""
    with driver.session() as s:
        records = s.run("""
            MATCH (q:QGIS_Operator)
            RETURN q.name AS name, q.description AS description,
                   q.algorithm_id AS algorithm_id
        """)
        result = {}
        for r in records:
            name = r["name"]
            desc = r["description"] or ""
            aid = r["algorithm_id"] or ""
            result[name] = {"description": desc, "algorithm_id": aid}
    print(f"[OK] Loaded {len(result)} QGIS operators")
    return result


def fetch_existing_mappings(driver) -> list:
    """返回 [(qgis_name, l3_code, confidence), ...]"""
    with driver.session() as s:
        records = s.run("""
            MATCH (q:QGIS_Operator)-[r:maps_to_l3]->(l:L3_Primitive)
            RETURN q.name AS qgis_name, l.code AS l3_code,
                   r.confidence AS confidence
        """)
        result = [(r["qgis_name"], r["l3_code"], r["confidence"]) for r in records]
    print(f"[OK] Loaded {len(result)} existing maps_to_l3 relationships")
    return result


def build_text(name: str, description: str) -> str:
    """合并名称和描述为模型输入文本"""
    if description:
        return f"{name}: {description}"
    return name


def main():
    # ── 1. 连接 Neo4j & 读取数据 ─────────────────────────────
    driver = connect_neo4j()
    l3_data = fetch_l3_descriptions(driver)
    qgis_data = fetch_qgis_descriptions(driver)
    mappings = fetch_existing_mappings(driver)
    driver.close()

    # ── 2. 加载模型 & 编码文本 ────────────────────────────────
    from sentence_transformers import SentenceTransformer

    print("[INFO] Loading all-MiniLM-L6-v2 ...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # 构建 L3 文本
    l3_codes = sorted(l3_data.keys())
    l3_texts = [build_text(l3_data[c]["name"], l3_data[c]["description"]) for c in l3_codes]
    l3_code_to_idx = {c: i for i, c in enumerate(l3_codes)}

    # 构建 QGIS 文本
    qgis_names = sorted(qgis_data.keys())
    qgis_texts = [build_text(n, qgis_data[n]["description"]) for n in qgis_names]
    qgis_name_to_idx = {n: i for i, n in enumerate(qgis_names)}

    print(f"[INFO] Encoding {len(l3_texts)} L3 texts ...")
    l3_embeddings = model.encode(l3_texts, show_progress_bar=True, normalize_embeddings=True)

    print(f"[INFO] Encoding {len(qgis_texts)} QGIS texts ...")
    qgis_embeddings = model.encode(qgis_texts, show_progress_bar=True, normalize_embeddings=True)

    # ── 3. 对已有映射计算语义分数 ────────────────────────────
    # 按 L3 分组
    l3_mapping_groups = defaultdict(list)  # l3_code -> [(qgis_name, confidence)]
    for qgis_name, l3_code, confidence in mappings:
        l3_mapping_groups[l3_code].append((qgis_name, confidence))

    scores = {}
    mapped_l3_count = 0
    for l3_code in l3_codes:
        if l3_code not in l3_mapping_groups:
            continue
        mapped_l3_count += 1
        l3_idx = l3_code_to_idx[l3_code]
        l3_emb = l3_embeddings[l3_idx]

        entries = []
        for qgis_name, orig_conf in l3_mapping_groups[l3_code]:
            if qgis_name not in qgis_name_to_idx:
                continue
            q_idx = qgis_name_to_idx[qgis_name]
            q_emb = qgis_embeddings[q_idx]
            # 已 normalize，点积 = cosine similarity
            sem_score = float(np.dot(l3_emb, q_emb))
            entries.append({
                "qgis_name": qgis_name,
                "semantic_score": round(sem_score, 4),
                "original_confidence": round(float(orig_conf), 4),
            })

        # 按语义分数降序
        entries.sort(key=lambda e: e["semantic_score"], reverse=True)
        scores[l3_code] = entries

    print(f"[OK] Computed semantic scores for {mapped_l3_count} mapped L3 codes")

    # ── 4. 对未映射 L3 找 Top-5 最相似的 QGIS ────────────────
    unmapped_l3 = [c for c in l3_codes if c not in l3_mapping_groups]
    print(f"[INFO] {len(unmapped_l3)} L3 codes have no existing mapping")

    discovered = {}
    if len(unmapped_l3) > 0:
        # 批量计算相似度矩阵（unmapped L3 × all QGIS）
        unmapped_indices = [l3_code_to_idx[c] for c in unmapped_l3]
        unmapped_embs = l3_embeddings[unmapped_indices]  # (M, D)
        sim_matrix = np.dot(unmapped_embs, qgis_embeddings.T)  # (M, N)

        for i, l3_code in enumerate(unmapped_l3):
            top5_indices = np.argsort(sim_matrix[i])[::-1][:5]
            entries = []
            for q_idx in top5_indices:
                sem_score = float(sim_matrix[i, q_idx])
                entries.append({
                    "qgis_name": qgis_names[q_idx],
                    "semantic_score": round(sem_score, 4),
                })
            discovered[l3_code] = entries

    print(f"[OK] Discovered top-5 candidates for {len(discovered)} unmapped L3 codes")

    # ── 5. 输出 JSON ─────────────────────────────────────────
    output = {
        "version": "1.0",
        "model": "all-MiniLM-L6-v2",
        "stats": {
            "total_l3": len(l3_codes),
            "mapped_l3": mapped_l3_count,
            "unmapped_l3": len(unmapped_l3),
            "total_qgis": len(qgis_names),
            "total_relationships": len(mappings),
        },
        "scores": scores,
        "discovered_mappings": discovered,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Saved to {OUTPUT_PATH}")
    print(f"  - Mapped L3 with scores: {len(scores)}")
    print(f"  - Discovered mappings: {len(discovered)}")

    # ── 快速验证 ─────────────────────────────────────────────
    print("\n=== Quick Verification ===")
    test_cases = ["L3_04_01_01", "L3_03_03_01", "L3_01_03_04"]
    for l3_code in test_cases:
        if l3_code in scores and scores[l3_code]:
            top = scores[l3_code][0]
            print(f"  {l3_code} ({l3_data.get(l3_code, {}).get('name', '?')})")
            print(f"    → Top QGIS: {top['qgis_name']} "
                  f"(sem={top['semantic_score']:.3f}, orig={top['original_confidence']:.3f})")


if __name__ == "__main__":
    main()
