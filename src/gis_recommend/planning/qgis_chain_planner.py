# -*- coding: utf-8 -*-
"""QGIS Chain Retriever + Evaluator — L3 planning → QGIS operator grounding.

Retriever:
    Input:  task_text + L3 token sequence
    Pool:   qgis_chain_dataset.jsonl
    Score:  text similarity + L3 overlap + vec/rast type + transition freq
    Output: top-k QGIS algorithm-id chains

Evaluator:
    Input:  QGIS algorithm-id chain
    Check:  catalog coverage, vec/rast consistency, duplicate ops,
            rare transitions, length sanity
    Output: quality score + flags

Usage:
    from gis_recommend.planning.qgis_chain_planner import QGISChainRetriever, QGISChainEvaluator

    retriever = QGISChainRetriever(dataset_path)
    candidates = retriever.retrieve(task_text="buffer and clip roads", l3_tokens=[...], k=10)

    evaluator = QGISChainEvaluator(catalog, transition_stats)
    result = evaluator.evaluate(candidates[0]["qgis_ops"])
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Retriever
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class QGISChainCandidate:
    qgis_ops: list[str]
    operator_names: list[str]
    task_text: str
    source: str
    quality: dict
    score: float = 0.0
    score_components: dict[str, float] = field(default_factory=dict)
    l3_sequence: list[str] | None = None


class QGISChainRetriever:
    """Retrieve QGIS chains from the dataset given task text + L3 tokens."""

    def __init__(
        self,
        dataset_path: Path | str,
        l3_to_qgis_names: dict[str, list[str]] | None = None,
        text_fields: list[str] | None = None,
    ):
        self.dataset = []
        self._text_index: list[set[str]] = []
        self._op_index: list[set[str]] = []
        self._l3_index: list[set[str]] = []
        self._native_bridge_index: list[set[str]] = []
        self._semantic_tag_index: list[set[str]] = []
        self._transition_freq: dict[tuple[str, str], float] = defaultdict(float)
        self._op_freq: Counter = Counter()

        if text_fields is None:
            text_fields = ["task_text", "task_description_en", "task_description_query", "task_text_original"]

        dataset_path = Path(dataset_path)
        if dataset_path.exists():
            with dataset_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    self.dataset.append(item)
                    # Merge all text fields for richer indexing
                    text_parts = []
                    for tf in text_fields:
                        val = item.get(tf, "")
                        if val and len(str(val)) > 2:
                            text_parts.append(str(val))
                    combined_text = " ".join(text_parts)
                    self._text_index.append(self._tokenize(combined_text))
                    self._op_index.append(set(item.get("qgis_ops", [])))
                    l3_seq = item.get("optional_l3_sequence", [])
                    self._l3_index.append(set(l3_seq if l3_seq else []))
                    sem_tags = item.get("qgis_semantic_tags", [])
                    self._semantic_tag_index.append(set(sem_tags if sem_tags else []))
                    # QGIS-native bridge tokens (landing-only, not L3)
                    native_bridges = self._derive_native_bridges(item)
                    self._native_bridge_index.append(native_bridges)

                    # Transition stats
                    ops = item.get("qgis_ops", [])
                    for op in ops:
                        self._op_freq[op] += 1
                    for a, b in zip(ops, ops[1:]):
                        self._transition_freq[(a, b)] += 1

        # Normalize transition counts to frequencies
        total_trans = max(sum(self._transition_freq.values()), 1)
        for k in self._transition_freq:
            self._transition_freq[k] = self._transition_freq[k] / total_trans

        self.l3_to_qgis_names = l3_to_qgis_names or {}

    def _tokenize(self, text: str) -> set[str]:
        tokens = set()
        for t in re.findall(r"[a-zA-Z0-9_]{2,}", str(text).lower()):
            tokens.add(t)
        return tokens

    def retrieve(
        self,
        task_text: str = "",
        l3_tokens: list[int] | None = None,
        l3_codes: list[str] | None = None,
        prefer_vector: bool = False,
        prefer_raster: bool = False,
        prefer_mixed: bool = False,
        k: int = 10,
        evaluator=None,
    ) -> list[QGISChainCandidate]:
        query_tokens = self._tokenize(task_text)
        l3_set = set(l3_codes or [])

        scored: list[QGISChainCandidate] = []
        for idx, item in enumerate(self.dataset):
            text_sim = self._jaccard(query_tokens, self._text_index[idx]) if query_tokens else 0.0
            # Operator keyword match: short user queries need operator-level matching
            op_match = 0.0
            if query_tokens:
                op_text = " ".join(item.get("qgis_ops", [])).replace(":", " ")
                op_tokens = self._tokenize(op_text)
                op_match = self._jaccard(query_tokens, op_tokens) if op_tokens else 0.0
            query_has_ops = bool(query_tokens and op_tokens)
            l3_overlap = (
                len(l3_set & self._l3_index[idx]) / max(len(l3_set), 1)
                if l3_set and self._l3_index[idx]
                else 0.0
            )

            q = item.get("quality", {})
            modality = item.get("modality", "")
            is_vec = bool(q.get("is_pure_vector")) or modality == "pure_vector"
            is_rast = bool(q.get("is_pure_raster")) or modality == "pure_raster"
            is_mixed = bool(q.get("is_mixed")) or modality == "mixed"
            type_bonus = 0.0
            if prefer_mixed and is_mixed:
                type_bonus = 0.15
            elif prefer_vector and is_vec:
                type_bonus = 0.15
            elif prefer_raster and is_rast:
                type_bonus = 0.15

            ops = item.get("qgis_ops", [])
            n = len(ops)

            # Transition frequency score
            trans_score = 0.0
            for a, b in zip(ops, ops[1:]):
                trans_score += self._transition_freq.get((a, b), 0.0)
            trans_score = trans_score / max(n - 1, 1)

            # Duplicate penalty
            n_unique = len(set(ops))
            dup_extra = max(0, n - n_unique)
            dup_penalty = min(0.25, 0.08 * dup_extra)

            # Consecutive duplicate penalty (stronger)
            consec_dup = sum(1 for i in range(n - 1) if ops[i] == ops[i + 1])
            consec_penalty = min(0.35, 0.15 * consec_dup)

            # Length bonus (prefer 3-8 step chains)
            len_bonus = 0.0
            if 3 <= n <= 8:
                len_bonus = 0.10
            elif n < 3:
                len_bonus = -0.05

            # Semantic tag score: matched-by-L3-or-query bonus (not unconditional)
            l3_derived_tags = self._infer_tags_from_l3(l3_set) if l3_set else set()
            query_derived_tags = self._infer_tags_from_query(query_tokens) if query_tokens else set()
            expected_tags = l3_derived_tags | query_derived_tags
            chain_tags = self._semantic_tag_index[idx] if idx < len(self._semantic_tag_index) else set()
            sem_tag_match = len(expected_tags & chain_tags) / max(len(expected_tags), 1) if expected_tags else 0.0
            sem_tag_bonus = 0.08 * sem_tag_match

            # Native bridge bonus: QGIS-native pseudo bridges (e.g. reprojectlayer)
            native_bridges = self._native_bridge_index[idx] if idx < len(self._native_bridge_index) else set()
            native_bridge_bonus = 0.08 if native_bridges else 0.0

            retrieval_score = (
                0.10 * text_sim
                + 0.30 * l3_overlap
                + (0.25 * op_match if not l3_set else 0.05 * op_match)  # boost when no L3 codes
                + type_bonus
                + 0.10 * trans_score
                + sem_tag_bonus
                + native_bridge_bonus
                + len_bonus
                - dup_penalty
                - consec_penalty
            )

            # Fuse evaluator quality if available
            evaluator_quality = 0.0
            if evaluator is not None:
                ev = evaluator.evaluate(ops)
                evaluator_quality = ev.quality_score

            final_score = retrieval_score + 0.20 * evaluator_quality

            candidate_task_text = item.get("task_description_en") or item.get("task_text") or item.get("task_text_original", "")
            candidate = QGISChainCandidate(
                qgis_ops=list(ops),
                operator_names=list(item.get("operator_names", [])),
                task_text=candidate_task_text,
                source=item.get("source", ""),
                quality=item.get("quality", {}),
                score=final_score,
                score_components={
                    "text_sim": round(text_sim, 4),
                    "l3_overlap": round(l3_overlap, 4),
                    "type_bonus": round(type_bonus, 4),
                    "trans_score": round(trans_score, 4),
                    "sem_tag_bonus": round(sem_tag_bonus, 4),
                    "native_bridge_bonus": round(native_bridge_bonus, 4),
                    "len_bonus": round(len_bonus, 4),
                    "dup_penalty": round(-dup_penalty, 4),
                    "consec_dup_penalty": round(-consec_penalty, 4),
                    "eval_quality": round(evaluator_quality, 4),
                    "retrieval_raw": round(retrieval_score, 4),
                },
                l3_sequence=list(item.get("optional_l3_sequence", [])) if item.get("optional_l3_sequence") else None,
            )
            scored.append(candidate)

        # Dedup by tuple(qgis_ops), keep highest score
        seen: dict[tuple[str, ...], QGISChainCandidate] = {}
        for c in scored:
            key = tuple(c.qgis_ops)
            if key not in seen or c.score > seen[key].score:
                seen[key] = c

        scored = sorted(seen.values(), key=lambda c: c.score, reverse=True)
        return scored[:k]

    # Semantic tag mapping — derives expected QGIS semantic categories from L3 codes
    _L3_TO_SEMANTIC_TAGS: dict[str, list[str]] = {
        "L3_01_02_03": ["coordinate_transform", "field_restructure", "field_rename"],
        "L3_02_01_01": ["buffer_variant", "proximity_analysis"],
        "L3_02_02_05": ["spatial_overlay"],
        "L3_02_02_06": ["spatial_overlay"],
        "L3_02_03_05": ["geometry_merge"],
        "L3_02_04_01": ["spatial_join", "table_join"],
        "L3_02_05_11": ["geometry_conversion", "geometry_vertices"],
        "L3_02_05_12": ["bounding_geometry"],
        "L3_02_06_01": ["attribute_select"],
        "L3_02_06_02": ["attribute_filter"],
        "L3_02_06_03": ["spatial_filter", "spatial_select"],
        "L3_02_07_01": ["geometry_repair", "geometry_explode", "geometry_merge"],
        "L3_01_03_04": ["layer_merge"],
        "L3_03_01_01": ["rasterize_convert", "polygonize_convert"],
        "L3_03_01_02": ["coordinate_transform"],
        "L3_03_05_02": ["coordinate_transform"],
        "L3_03_02_01": ["zonal_statistics"],
        "L3_03_03_A": ["raster_calc", "gap_fill"],
        "L3_03_04_01": ["reclassify"],
        "L3_04_01_01": ["surface_derivative", "terrain_analysis"],
        "L3_07_04_01": ["data_export"],
        "L3_07_04_05": ["data_export", "format_conversion"],
        "L3_08_01_01": ["sampling"],
    }

    _QUERY_KW_TO_TAGS: dict[str, str] = {
        "buffer": "proximity_analysis",
        "clip": "spatial_clip",
        "dissolve": "geometry_merge",
        "merge": "layer_merge",
        "intersect": "spatial_overlay",
        "reproject": "coordinate_transform",
        "fix": "geometry_repair",
        "simplify": "geometry_simplify",
        "voronoi": "voronoi",
        "thiessen": "voronoi",
        "join": "spatial_join",
        "select": "attribute_select",
        "extract": "attribute_filter",
        "rasterize": "rasterize_convert",
        "polygonize": "polygonize_convert",
        "slope": "terrain_analysis",
        "hillshade": "terrain_analysis",
        "contour": "surface_derivative",
        "ndvi": "vegetation_index",
        "zonal": "zonal_statistics",
        "warp": "coordinate_transform",
        "mosaic": "mosaic",
        "save": "data_export",
        "export": "data_export",
        "centroid": "centroid_extract",
        "label": "labeling",
        "grid": "grid_generation",
        "heatmap": "density_heatmap",
        "nearest": "nearest_neighbor",
        "distance": "proximity_analysis",
        "erase": "spatial_overlay",
        "difference": "spatial_overlay",
        "sample": "raster_sampling",
        "snap": "geometry_repair",
        "smooth": "geometry_simplify",
        "hole": "geometry_cleanup",
        "delaunay": "triangulation",
        "concave": "concave_hull",
        "convex": "convex_hull",
        "filter": "attribute_filter",
        "count": "aggregation",
        "aggregate": "aggregation",
        "summarize": "zonal_statistics",
        "field": "field_calculate",
        "calculate": "field_calculate",
    }

    def _infer_tags_from_l3(self, l3_codes: set[str]) -> set[str]:
        tags: set[str] = set()
        for code in l3_codes:
            for tag in self._L3_TO_SEMANTIC_TAGS.get(code, []):
                tags.add(tag)
        return tags

    def _infer_tags_from_query(self, query_tokens: set[str]) -> set[str]:
        tags: set[str] = set()
        for token in query_tokens:
            for kw, tag in self._QUERY_KW_TO_TAGS.items():
                if kw in token:
                    tags.add(tag)
        return tags

    # ── Native bridge detection ─────────────────────────────────────
    # QGIS operators that lack L3 mapping but have clear semantic intent.
    # Tagged as landing-only pseudo bridges so the retriever can find them.
    NATIVE_BRIDGE_MAP: dict[str, str] = {
        "reprojectlayer": "qgis_native:vector_crs_transform",
    }

    def _derive_native_bridges(self, item: dict) -> set[str]:
        bridges: set[str] = set()
        for op in item.get("qgis_ops", []):
            name_lower = op.lower().replace("native:", "").replace("qgis:", "").replace("gdal:", "")
            for kw, tag in self.NATIVE_BRIDGE_MAP.items():
                if kw in name_lower:
                    bridges.add(tag)
        return bridges

    def _jaccard(self, a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def stats(self) -> dict:
        return {
            "num_chains": len(self.dataset),
            "num_unique_ops": len(self._op_freq),
            "top_ops": dict(self._op_freq.most_common(20)),
            "top_transitions": [
                {"pair": list(k), "freq": round(v, 6)}
                for k, v in sorted(
                    self._transition_freq.items(), key=lambda x: -x[1]
                )[:20]
            ],
        }


# ═══════════════════════════════════════════════════════════════════════
# Evaluator
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class QGISChainEval:
    qgis_ops: list[str]
    quality_score: float = 0.0
    flags: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    is_valid: bool = True


class QGISChainEvaluator:
    """Evaluate QGIS operator chain quality without execution."""

    def __init__(
        self,
        catalog: dict[str, dict] | None = None,
        transition_freq: dict[tuple[str, str], float] | None = None,
    ):
        self.catalog = catalog or {}
        self.transition_freq = transition_freq or {}

    def evaluate(self, qgis_ops: list[str]) -> QGISChainEval:
        n = len(qgis_ops)
        flags = []
        score = 1.0

        if n == 0:
            return QGISChainEval(
                qgis_ops=qgis_ops, quality_score=0.0,
                flags=["empty_chain"], is_valid=False,
            )

        # 1) Catalog coverage
        in_catalog = sum(1 for op in qgis_ops if op.lower() in self.catalog)
        catalog_rate = in_catalog / n
        details = {"catalog_coverage": catalog_rate}
        if catalog_rate < 0.9:
            flags.append(f"low_catalog_coverage_{catalog_rate:.2f}")
            score -= 0.25 * (1.0 - catalog_rate)

        # 2) Duplicate check
        dup_count = len(qgis_ops) - len(set(qgis_ops))
        details["duplicate_extra"] = dup_count
        if dup_count > 0:
            flags.append(f"duplicate_operators_{dup_count}")
            score -= min(0.30, 0.10 * dup_count)

        # Consecutive duplicates
        consec_dup = sum(
            1 for i in range(n - 1) if qgis_ops[i] == qgis_ops[i + 1]
        )
        details["consecutive_duplicates"] = consec_dup
        if consec_dup > 0:
            flags.append(f"consecutive_duplicate_{consec_dup}")
            score -= min(0.40, 0.20 * consec_dup)

        # 3) Vector/raster consistency
        types = []
        for op in qgis_ops:
            cat = self.catalog.get(op.lower(), {})
            types.append(cat.get("data_type", "unknown"))
        vec_count = sum(1 for t in types if t == "vector")
        rast_count = sum(1 for t in types if t == "raster")
        details["vector_ops"] = vec_count
        details["raster_ops"] = rast_count

        if vec_count > 0 and rast_count > 0:
            flags.append("mixed_vec_raster")
            details["is_mixed"] = True
            # Check for bridge operators
            has_bridge = any(
                kw in op.lower() for op in qgis_ops
                for kw in ["rasterize", "polygonize", "warp", "reproject", "clipraster", "zonal", "pixelstopolygons"]
            )
            details["has_vec_rast_bridge"] = has_bridge
            if not has_bridge:
                flags.append("vec_raster_no_bridge")
                score -= 0.15

        # 4) Rare transition detection
        rare_count = 0
        for a, b in zip(qgis_ops, qgis_ops[1:]):
            freq = self.transition_freq.get((a, b), 0.0)
            if freq == 0.0:
                rare_count += 1
        details["rare_transitions"] = rare_count
        if rare_count > n // 2:
            flags.append(f"many_rare_transitions_{rare_count}")
            score -= 0.10

        # 5) Length sanity
        details["length"] = n
        if n < 2:
            flags.append("too_short")
            score -= 0.10
        elif n > 20:
            flags.append("very_long")
            score -= 0.10

        # 6) Operator frequency (low = exotic)
        details["op_freq_summary"] = {}
        details["is_valid"] = True

        quality_score = max(0.0, min(1.0, score))
        return QGISChainEval(
            qgis_ops=qgis_ops,
            quality_score=round(quality_score, 4),
            flags=flags,
            details=details,
            is_valid=quality_score >= 0.5,
        )


# ═══════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════

def build_qgis_chain_planner(
    dataset_path: Path | str,
    catalog_path: Path | str | None = None,
) -> tuple[QGISChainRetriever, QGISChainEvaluator]:
    """Build retriever + evaluator from dataset and catalog."""
    # Load catalog if provided
    catalog = {}
    if catalog_path:
        catalog_path = Path(catalog_path)
        if catalog_path.exists():
            import csv
            with catalog_path.open("r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 6:
                        continue
                    alg_id = row[5].strip().lower()
                    name = row[2].strip() if len(row) > 2 else ""
                    platform = row[0].strip()
                    data_type = "unknown"
                    for col in row[8:]:
                        if col.strip() in ("vector", "raster"):
                            data_type = col.strip()
                            break
                    if alg_id:
                        catalog[alg_id] = {
                            "name": name, "platform": platform,
                            "data_type": data_type, "alg_id": alg_id,
                        }

    retriever = QGISChainRetriever(dataset_path)
    evaluator = QGISChainEvaluator(
        catalog=catalog,
        transition_freq=dict(retriever._transition_freq),
    )
    return retriever, evaluator
