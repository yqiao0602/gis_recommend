#!/usr/bin/env python3
"""Evaluate workflow usability beyond sequence-level similarity.

Measures whether retrieval-centered workflow planning already produces
practically usable QGIS operator chains using STRICT rule-based validation.

NO training. NO checkpoint modification. NO architecture redesign.
NO semantic retrieval. NO ontology expansion. NO LLM judging.
NO execution simulation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SCHEMA_VERSION = "gis_recommend.v5_final.workflow_usability.v1"
SPECIAL_TOKENS = {-1, -2, -3, -4}


# ===========================================================================
# Data Loading
# ===========================================================================

def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", payload)
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid workflows payload: {path}")
    return workflows


def _load_csv(path: Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return [int(t) for t in tokens if int(t) not in SPECIAL_TOKENS]


def _task_type(wf: dict) -> str:
    tm = wf.get("task_metadata", {})
    return str(tm.get("task_type_normalized", tm.get("task_type", "Unknown")))


def _task_text(wf: dict) -> str:
    tm = wf.get("task_metadata", {})
    parts = [
        str(tm.get("task_name", "")),
        str(tm.get("task_description", "")),
        str(tm.get("task_type_normalized", tm.get("task_type", ""))),
    ]
    return " ".join(part for part in parts if part).strip()


def _tokenize_query_text(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[A-Za-z0-9_]+", str(text).lower()):
        if len(token) <= 1:
            continue
        tokens.add(token)
    return tokens


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


# ===========================================================================
# Operator Role Classification (from L1/L2 hierarchy categories)
# ===========================================================================

DATA_SOURCE_L2 = {"L2_01_01", "L2_01_03"}
FILTER_L2 = {"L2_02_06", "L2_03_01", "L2_03_09"}
COMPUTE_L2 = {
    "L2_02_01", "L2_02_02", "L2_03_03", "L2_03_04", "L2_03_05",
    "L2_03_07", "L2_03_08", "L2_03_10", "L2_08_02", "L2_08_03",
    "L2_08_04", "L2_04_01", "L2_07_01", "L2_07_04",
}
EXPORT_L2 = {
    "L2_10_02", "L2_10_03", "L2_10_04", "L2_10_06",
    "L2_09_03", "L2_09_05", "L2_09_06", "L2_09_07", "L2_09_09",
}
AGGREGATION_L2 = {
    "L2_01_08", "L2_02_03", "L2_02_04", "L2_03_02", "L2_03_06",
    "L2_03_11", "L2_08_01", "L2_08_05",
}
BRIDGE_L2 = {"L2_03_12", "L2_03_13"}
VISUALIZATION_L2 = EXPORT_L2 | {"L2_08_07"}

L1_RASTER = "L1_03"
L1_VECTOR = "L1_02"


def build_token_roles(hierarchy_rows: list[dict], code_to_id: dict) -> dict[int, dict]:
    roles = {}
    for row in hierarchy_rows:
        l3 = row.get("l3_code", "")
        l2 = row.get("l2_code", "")
        l1 = row.get("l1_code", "")
        tid = code_to_id.get(l3)
        if tid is None:
            continue
        roles[int(tid)] = {
            "is_data_source": l2 in DATA_SOURCE_L2,
            "is_filter": l2 in FILTER_L2,
            "is_compute": l2 in COMPUTE_L2,
            "is_export": l2 in EXPORT_L2,
            "is_aggregation": l2 in AGGREGATION_L2,
            "is_bridge": l2 in BRIDGE_L2,
            "is_visualization": l2 in VISUALIZATION_L2,
            "l1_code": l1,
            "l2_code": l2,
            "l3_code": l3,
        }
    return roles


# ===========================================================================
# QGIS Mapping
# ===========================================================================

def build_qgis_mapping(id_mappings: dict, code_to_id: dict) -> dict[int, list[str]]:
    l3_to_qgis: dict[str, list[str]] = {}
    q2l3 = (id_mappings.get("mapping_metadata") or {}).get("qgis_to_l3") or {}
    for qgis_name, info in q2l3.items():
        if not isinstance(info, dict):
            continue
        primary = info.get("primary_l3", "")
        if primary:
            l3_to_qgis.setdefault(primary, []).append(qgis_name)
        for cand in info.get("all_candidates") or []:
            l3c = cand.get("l3_code", "") if isinstance(cand, dict) else ""
            if l3c:
                l3_to_qgis.setdefault(l3c, []).append(qgis_name)
    token_to_qgis: dict[int, list[str]] = {}
    for l3_code, qgis_list in l3_to_qgis.items():
        tid = code_to_id.get(l3_code)
        if tid is not None:
            token_to_qgis[int(tid)] = list(set(qgis_list))
    return token_to_qgis


# ===========================================================================
# Critical Operators per Task Type
# ===========================================================================

def compute_critical_operators(
    workflows: list[dict], threshold: float = 0.30
) -> dict[str, set[int]]:
    by_task: dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for wf in workflows:
        task = _task_type(wf)
        tokens = set(_content_tokens(wf.get("l3_sequence", [])))
        totals[task] += 1
        for t in tokens:
            by_task[task][t] += 1
    return {
        task: {t for t, c in counts.items() if c / max(totals[task], 1) >= threshold}
        for task, counts in by_task.items()
    }


def build_commutative_pairs(workflows: list[dict]) -> set[tuple[int, int]]:
    adj_by_task: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for wf in workflows:
        task = _task_type(wf)
        seq = _content_tokens(wf.get("l3_sequence", []))
        for a, b in zip(seq, seq[1:]):
            adj_by_task[task].add((a, b))
    pairs = set()
    for adj in adj_by_task.values():
        for a, b in adj:
            if a != b and (b, a) in adj:
                pairs.add(tuple(sorted((a, b))))
    return pairs


# ===========================================================================
# Usability Evaluation
# ===========================================================================

@dataclass
class UsabilityResult:
    required_step_coverage: float = 0.0
    harmful_step_rate: float = 0.0
    harmful_details: list[str] = field(default_factory=list)
    missing_critical_step_rate: float = 0.0
    missing_steps: list[int] = field(default_factory=list)
    executable_qgis_mapping_rate: float = 0.0
    unmappable_tokens: list[int] = field(default_factory=list)
    workflow_logic_consistency: float = 0.0
    logic_violations: list[str] = field(default_factory=list)
    redundancy_rate: float = 0.0
    redundant_positions: list[int] = field(default_factory=list)
    usable: bool = False
    usability_score: float = 0.0
    forbidden_patterns: list[str] = field(default_factory=list)
    failure_taxonomy: list[str] = field(default_factory=list)


class UsabilityEvaluator:
    def __init__(
        self,
        hierarchy_path: Path,
        id_mappings_path: Path,
        l3_vocab_path: Path,
        train_workflows: list[dict],
    ):
        hierarchy = _load_csv(hierarchy_path)
        vocab = _load_json(l3_vocab_path)
        self.code_to_id = vocab.get("code_to_id", {})
        self.id_to_code = vocab.get("id_to_code", [])

        id_map = _load_json(id_mappings_path)
        self.token_roles = build_token_roles(hierarchy, self.code_to_id)
        self.token_qgis = build_qgis_mapping(id_map, self.code_to_id)
        self.token_has_qgis = {tid: bool(v) for tid, v in self.token_qgis.items()}

        self.task_critical = compute_critical_operators(train_workflows, threshold=0.30)
        self.task_frequent = compute_critical_operators(train_workflows, threshold=0.15)
        self.commutative_pairs = build_commutative_pairs(train_workflows)

    def _role(self, token: int) -> dict:
        return self.token_roles.get(token, {})

    # -- Metric A: required_step_coverage --
    def required_step_coverage(self, tokens: Sequence[int], task: str) -> tuple[float, list[int]]:
        content = set(_content_tokens(tokens))
        critical = self.task_critical.get(task, set())
        if not critical:
            return 1.0, []
        present = content & critical
        return len(present) / len(critical), sorted(critical - present)

    # -- Metric B: harmful_step_rate --
    def harmful_step_rate(self, tokens: Sequence[int]) -> tuple[float, list[str]]:
        content = _content_tokens(tokens)
        if not content:
            return 1.0, ["empty_workflow"]
        harmful = []
        for i, t in enumerate(content):
            r = self._role(t)
            if i == 0 and r.get("is_export"):
                harmful.append(f"pos{i}_t{t}:first_step_export")
            if i > 1 and r.get("is_data_source"):
                harmful.append(f"pos{i}_t{t}:data_source_mid_workflow")
            if r.get("is_bridge"):
                nearby = content[max(0, i - 2):i] + content[i + 1:i + 3]
                nearby_l1 = {self._role(n).get("l1_code") for n in nearby}
                if L1_RASTER not in nearby_l1 or L1_VECTOR not in nearby_l1:
                    harmful.append(f"pos{i}_t{t}:orphan_bridge")
        return len(harmful) / len(content), harmful

    # -- Metric C: missing_critical_step_rate --
    def missing_critical_step_rate(self, tokens: Sequence[int], task: str) -> tuple[float, list[int]]:
        cov, missing = self.required_step_coverage(tokens, task)
        return 1.0 - cov, missing

    # -- Metric D: executable_qgis_mapping_rate --
    def executable_qgis_mapping_rate(self, tokens: Sequence[int]) -> tuple[float, list[int]]:
        content = _content_tokens(tokens)
        if not content:
            return 0.0, []
        unmapped = [t for t in content if not self.token_has_qgis.get(t, False)]
        return 1.0 - len(unmapped) / len(content), unmapped

    # -- Metric E: workflow_logic_consistency --
    def workflow_logic_consistency(self, tokens: Sequence[int]) -> tuple[float, list[str]]:
        content = _content_tokens(tokens)
        if not content:
            return 0.0, ["empty_workflow"]
        violations = []
        checks_total = 0

        for i in range(len(content) - 1):
            cr = self._role(content[i])
            nr = self._role(content[i + 1])
            if cr.get("is_compute") and nr.get("is_filter"):
                pair = tuple(sorted((content[i], content[i + 1])))
                if pair not in self.commutative_pairs:
                    violations.append(f"pos{i}:compute_before_filter(t{content[i]},t{content[i+1]})")
            checks_total += 1

        for i, t in enumerate(content):
            r = self._role(t)
            if r.get("is_export") and i < len(content) * 0.3:
                violations.append(f"pos{i}_t{t}:export_too_early")
                checks_total += 1
            if r.get("is_data_source") and i > len(content) * 0.6:
                violations.append(f"pos{i}_t{t}:data_source_too_late")
                checks_total += 1
            if r.get("l2_code") == "L2_03_10":
                has_filter = any(
                    self._role(content[j]).get("is_filter")
                    for j in range(max(0, i - 3), i)
                )
                if not has_filter and i > 0:
                    violations.append(f"pos{i}_t{t}:composite_no_preceding_filter")
                checks_total += 1

        has_compute = any(self._role(t).get("is_compute") for t in content)
        has_agg = any(self._role(t).get("is_aggregation") for t in content)
        if not has_compute and not has_agg:
            violations.append("no_compute_step")
            checks_total += 1

        total = max(checks_total, len(violations), 1)
        return max(0.0, 1.0 - len(violations) / total), violations

    # -- Metric G: redundancy_rate --
    def redundancy_rate(self, tokens: Sequence[int]) -> tuple[float, list[int]]:
        content = _content_tokens(tokens)
        if not content:
            return 0.0, []
        dup_pos = [i for i in range(1, len(content)) if content[i] == content[i - 1]]
        return len(dup_pos) / len(content), dup_pos

    # -- Forbidden pattern scan --
    def scan_forbidden_patterns(self, tokens: Sequence[int]) -> list[str]:
        content = _content_tokens(tokens)
        triggered = []

        # FP01 compute before non-commutative filter
        for i in range(len(content) - 1):
            cr = self._role(content[i])
            nr = self._role(content[i + 1])
            if cr.get("is_compute") and nr.get("is_filter"):
                pair = tuple(sorted((content[i], content[i + 1])))
                if pair not in self.commutative_pairs:
                    triggered.append("FP01:filter_after_compute")
                    break

        # FP02 export before processing
        export_pos = [i for i, t in enumerate(content) if self._role(t).get("is_export")]
        compute_pos = [i for i, t in enumerate(content) if self._role(t).get("is_compute")]
        if export_pos and compute_pos and min(export_pos) < min(compute_pos):
            triggered.append("FP02:export_before_processing")

        # FP03 data source in middle
        if any(self._role(content[i]).get("is_data_source") for i in range(2, len(content))):
            triggered.append("FP03:data_source_in_middle")

        # FP04 consecutive duplicate
        if any(content[i] == content[i + 1] for i in range(len(content) - 1)):
            triggered.append("FP04:consecutive_duplicate")

        # FP05 compute without data source
        has_source = any(self._role(t).get("is_data_source") or self._role(t).get("is_filter")
                        for t in content[:3])
        has_compute = any(self._role(t).get("is_compute") for t in content)
        if has_compute and not has_source:
            triggered.append("FP05:compute_without_source")

        # FP06 raster-vector mismatch without bridge
        l1s = {self._role(t).get("l1_code") for t in content}
        has_bridge = any(self._role(t).get("is_bridge") for t in content)
        if L1_RASTER in l1s and L1_VECTOR in l1s and not has_bridge:
            triggered.append("FP06:raster_vector_mismatch_no_bridge")

        # FP08 degenerate
        if len(content) < 2 or len(content) > 50:
            triggered.append("FP08:degenerate_workflow")

        # FP09 export only
        meaningful = [t for t in content
                      if not self._role(t).get("is_export")
                      and not self._role(t).get("is_data_source")]
        if not meaningful and content:
            triggered.append("FP09:export_only")

        return triggered

    # -- Full evaluation --
    def evaluate(self, tokens: Sequence[int], task: str) -> UsabilityResult:
        cov, missing = self.required_step_coverage(tokens, task)
        hrate, hdetails = self.harmful_step_rate(tokens)
        mcrate, mcsteps = self.missing_critical_step_rate(tokens, task)
        erate, unmapped = self.executable_qgis_mapping_rate(tokens)
        logic, lviols = self.workflow_logic_consistency(tokens)
        rrate, rpos = self.redundancy_rate(tokens)
        forbidden = self.scan_forbidden_patterns(tokens)

        weights = {
            "coverage": 0.20, "executable": 0.25, "logic": 0.25,
            "harmful_inv": 0.15, "redundancy_inv": 0.05, "missing_inv": 0.10,
        }
        uscore = (
            weights["coverage"] * cov
            + weights["executable"] * erate
            + weights["logic"] * logic
            + weights["harmful_inv"] * (1.0 - hrate)
            + weights["redundancy_inv"] * (1.0 - rrate)
            + weights["missing_inv"] * (1.0 - mcrate)
        )

        critical_fp = [f for f in forbidden if f.startswith(("FP02", "FP05", "FP09"))]
        usable = uscore >= 0.6 and not critical_fp and erate >= 0.5

        ft = []
        if mcrate > 0.2:
            ft.append("missing_critical_steps")
        if hrate > 0.2:
            ft.append("harmful_steps")
        if erate < 0.5:
            ft.append("qgis_unmappable_steps")
        if logic < 0.5:
            ft.append("logic_inconsistency")
        if rrate > 0.25:
            ft.append("redundant_steps")
        if forbidden:
            ft.extend(forbidden)
        if not ft:
            ft.append("usable_no_failure" if usable else "unusable_marginal")

        return UsabilityResult(
            required_step_coverage=round(cov, 6),
            harmful_step_rate=round(hrate, 6),
            harmful_details=hdetails,
            missing_critical_step_rate=round(mcrate, 6),
            missing_steps=mcsteps,
            executable_qgis_mapping_rate=round(erate, 6),
            unmappable_tokens=unmapped,
            workflow_logic_consistency=round(logic, 6),
            logic_violations=lviols,
            redundancy_rate=round(rrate, 6),
            redundant_positions=rpos,
            usable=usable,
            usability_score=round(uscore, 6),
            forbidden_patterns=forbidden,
            failure_taxonomy=ft,
        )


# ===========================================================================
# Lexical Retrieval Baseline (model-free)
# ===========================================================================

class LexicalRetrieval:
    def __init__(self, train_workflows: list[dict]):
        self.by_task: dict[str, list[dict]] = defaultdict(list)
        self.by_task_tokens: dict[str, list[set[str]]] = defaultdict(list)
        self.global_workflows: list[dict] = []
        self.global_tokens: list[set[str]] = []
        for wf in train_workflows:
            task = _task_type(wf)
            self.by_task[task].append(wf)
            self.by_task_tokens[task].append(_tokenize_query_text(_task_text(wf)))
            self.global_workflows.append(wf)
            self.global_tokens.append(_tokenize_query_text(_task_text(wf)))

    def _score_workflow(self, query_tokens: set[str], wf: dict, wf_tokens: set[str]) -> float:
        task_name = _task_text(wf)
        token_overlap = _jaccard_similarity(query_tokens, wf_tokens)
        if not query_tokens:
            return 0.0
        task_type_bonus = 0.0
        wf_task = _task_type(wf).lower()
        if wf_task and wf_task in " ".join(query_tokens):
            task_type_bonus = 0.10
        name_tokens = _tokenize_query_text(task_name)
        name_bonus = 0.15 * _jaccard_similarity(query_tokens, name_tokens)
        return round(min(1.0, token_overlap + task_type_bonus + name_bonus), 6)

    def retrieve(self, task: str, query_text: str | None = None, k: int = 10) -> list[dict]:
        pool = self.by_task.get(task, [])
        pool_tokens = self.by_task_tokens.get(task, [])
        query_tokens = _tokenize_query_text(query_text or task)
        seen = set()
        scored = []
        for idx, wf in enumerate(pool):
            seq = tuple(_content_tokens(wf.get("l3_sequence", [])))
            if not seq or seq in seen:
                continue
            seen.add(seq)
            score = self._score_workflow(query_tokens, wf, pool_tokens[idx] if idx < len(pool_tokens) else set())
            scored.append({
                "tokens": list(seq),
                "rank": idx,
                "score": score,
                "retrieval_method": "query_jaccard",
                "task_type": task,
            })
        if len(scored) < k and self.global_workflows:
            global_seen = {tuple(row["tokens"]) for row in scored}
            supplement = []
            for idx, wf in enumerate(self.global_workflows):
                seq = tuple(_content_tokens(wf.get("l3_sequence", [])))
                if not seq or seq in global_seen:
                    continue
                score = self._score_workflow(query_tokens, wf, self.global_tokens[idx] if idx < len(self.global_tokens) else set())
                supplement.append({
                    "tokens": list(seq),
                    "rank": idx,
                    "score": score * 0.5,
                    "retrieval_method": "global_backoff_jaccard",
                    "task_type": _task_type(wf),
                })
            scored.extend(sorted(supplement, key=lambda row: (-row["score"], row["rank"], len(row["tokens"]))))
        scored.sort(key=lambda row: (-row["score"], row["rank"], len(row["tokens"])))
        results = []
        for row in scored:
            results.append(row)
            if len(results) >= k:
                break
        return results


class MarkovBaseline:
    def __init__(self, train_workflows: list[dict]):
        self.trans: dict[int, Counter] = defaultdict(Counter)
        self.starts: Counter = Counter()
        for wf in train_workflows:
            seq = _content_tokens(wf.get("l3_sequence", []))
            if seq:
                self.starts[seq[0]] += 1
                for a, b in zip(seq, seq[1:]):
                    self.trans[a][b] += 1

    def generate(self, k: int = 5, max_len: int = 15) -> list[list[int]]:
        results = []
        for start, _ in self.starts.most_common(k):
            seq = [start]
            cur = start
            for _ in range(max_len - 1):
                nxt = self.trans.get(cur)
                if not nxt:
                    break
                cur = nxt.most_common(1)[0][0]
                seq.append(cur)
            if len(seq) >= 2:
                results.append(seq)
        return results


# ===========================================================================
# Bootstrap
# ===========================================================================

def bootstrap_ci(values: list[float], n_boot: int = 1000, ci: float = 0.95) -> dict:
    if len(values) < 5:
        m = sum(values) / len(values) if values else 0.0
        return {"mean": m, "ci_lower": None, "ci_upper": None, "n_small": True}
    rng = random.Random(42)
    means = sorted(
        sum(rng.choice(values) for _ in values) / len(values)
        for _ in range(n_boot)
    )
    alpha = (1.0 - ci) / 2.0
    return {
        "mean": sum(values) / len(values),
        "ci_lower": round(means[int(alpha * n_boot)], 6),
        "ci_upper": round(means[int((1.0 - alpha) * n_boot)], 6),
        "n": len(values),
        "n_bootstrap": n_boot,
    }


# ===========================================================================
# Per-sample evaluation
# ===========================================================================

def evaluate_topk(
    candidates: list[dict],
    evaluator: UsabilityEvaluator,
    task: str,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict:
    out = {}
    for k in ks:
        topk = candidates[:k]
        per = []
        for cand in topk:
            tk = cand.get("tokens", [])
            r = evaluator.evaluate(tk, task)
            per.append({
                "tokens": tk,
                "required_step_coverage": r.required_step_coverage,
                "harmful_step_rate": r.harmful_step_rate,
                "missing_critical_step_rate": r.missing_critical_step_rate,
                "executable_qgis_mapping_rate": r.executable_qgis_mapping_rate,
                "workflow_logic_consistency": r.workflow_logic_consistency,
                "redundancy_rate": r.redundancy_rate,
                "usability_score": r.usability_score,
                "usable": r.usable,
                "forbidden_patterns": r.forbidden_patterns,
                "failure_taxonomy": r.failure_taxonomy,
                "logic_violations": r.logic_violations,
                "harmful_details": r.harmful_details,
                "missing_steps": r.missing_steps,
            })
        usable_n = sum(1 for c in per if c["usable"])
        scores = [c["usability_score"] for c in per]
        out[f"top{k}"] = {
            "per_candidate": per,
            "best_usability_score": round(max(scores), 6) if scores else 0.0,
            "any_usable": usable_n > 0,
            "usable_count": usable_n,
            "usable_rate": round(usable_n / len(per), 6) if per else 0.0,
            "avg_usability_score": round(sum(scores) / len(scores), 6) if scores else 0.0,
        }
    return out


# ===========================================================================
# Main Pipeline
# ===========================================================================

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def qgis_mapped_tokens_from_id_mappings(id_mappings: dict) -> set[int]:
    code_to_id = id_mappings.get("l3", {})
    mapped = set()
    qgis_to_l3 = (id_mappings.get("mapping_metadata") or {}).get("qgis_to_l3") or {}
    for info in qgis_to_l3.values():
        if not isinstance(info, dict):
            continue
        primary = info.get("primary_l3")
        if primary in code_to_id:
            mapped.add(int(code_to_id[primary]))
        for candidate in info.get("all_candidates") or []:
            if not isinstance(candidate, dict):
                continue
            l3_code = candidate.get("l3_code")
            if l3_code in code_to_id:
                mapped.add(int(code_to_id[l3_code]))
    return mapped


def evaluate_candidate_usability(
    pred_tokens: Sequence[int],
    ref_tokens: Sequence[int],
    qgis_mapped_tokens: set[int],
) -> dict:
    pred = _content_tokens(pred_tokens)
    ref = _content_tokens(ref_tokens)
    ref_set = set(ref)
    pred_set = set(pred)
    required_step_coverage = len(pred_set & ref_set) / max(len(ref_set), 1)
    missing_critical_step_rate = 1.0 - required_step_coverage
    unmapped = [token for token in pred if int(token) not in qgis_mapped_tokens]
    executable_qgis_mapping_rate = 1.0 - len(unmapped) / max(len(pred), 1) if pred else 0.0
    duplicate_positions = [idx for idx in range(1, len(pred)) if pred[idx] == pred[idx - 1]]
    redundancy_rate = len(duplicate_positions) / max(len(pred), 1) if pred else 0.0
    harmful_step_rate = 0.0
    if not pred:
        harmful_step_rate = 1.0
    elif any(token not in ref_set and token not in qgis_mapped_tokens for token in pred):
        harmful_step_rate = len([token for token in pred if token not in ref_set and token not in qgis_mapped_tokens]) / len(pred)
    workflow_logic_consistency = max(0.0, 1.0 - redundancy_rate)
    usable = (
        required_step_coverage >= 0.6
        and executable_qgis_mapping_rate >= 0.5
        and harmful_step_rate <= 0.2
        and workflow_logic_consistency >= 0.5
    )
    failure_taxonomy = []
    if missing_critical_step_rate > 0.2:
        failure_taxonomy.append("missing_critical_steps")
    if harmful_step_rate > 0.2:
        failure_taxonomy.append("harmful_steps")
    if executable_qgis_mapping_rate < 0.5:
        failure_taxonomy.append("qgis_unmapped_steps")
    if redundancy_rate > 0.25:
        failure_taxonomy.append("redundant_steps")
    return {
        "required_step_coverage": round(required_step_coverage, 6),
        "harmful_step_rate": round(harmful_step_rate, 6),
        "missing_critical_step_rate": round(missing_critical_step_rate, 6),
        "executable_qgis_mapping_rate": round(executable_qgis_mapping_rate, 6),
        "workflow_logic_consistency": round(workflow_logic_consistency, 6),
        "redundancy_rate": round(redundancy_rate, 6),
        "usable": bool(usable),
        "failure_taxonomy": failure_taxonomy,
    }


def evaluate_records(
    records: Sequence[dict],
    qgis_mapped_tokens: set[int],
    bootstrap_iterations: int = 500,
    seed: int = 42,
) -> dict:
    by_method: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        method = str(record.get("method", "unknown"))
        ref = record.get("reference_tokens") or []
        pred = record.get("pred_tokens") or []
        topk = record.get("topk_candidates") or [pred]
        top1 = evaluate_candidate_usability(pred, ref, qgis_mapped_tokens)
        top3_any = any(evaluate_candidate_usability(cand, ref, qgis_mapped_tokens)["usable"] for cand in topk[:3])
        top5_any = any(evaluate_candidate_usability(cand, ref, qgis_mapped_tokens)["usable"] for cand in topk[:5])
        by_method[method].append({
            "top1": top1,
            "top3_any": float(top3_any),
            "top5_any": float(top5_any),
        })

    def _avg(values: Sequence[float]) -> float:
        return round(sum(values) / len(values), 6) if values else 0.0

    methods = {}
    for method, rows in by_method.items():
        top1_usable = [float(row["top1"]["usable"]) for row in rows]
        scores = [row["top1"]["required_step_coverage"] for row in rows]
        methods[method] = {
            "n": len(rows),
            "top1": {
                "usable_rate": _avg(top1_usable),
                "bootstrap": bootstrap_ci(top1_usable, n_boot=bootstrap_iterations),
            },
            "top3_usable_rate": _avg([row["top3_any"] for row in rows]),
            "top5_usable_rate": _avg([row["top5_any"] for row in rows]),
            "mean_required_step_coverage": _avg(scores),
            "topk_recovery_counts": {
                "top3_usable_not_top1": sum(
                    1 for row in rows if row["top3_any"] and not row["top1"]["usable"]
                ),
            },
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "methods": methods,
        "seed": int(seed),
    }


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    matches = []
    patterns = [r"\.backward\s*\(", r"optimizer\s*\.", r"torch\.optim", r"checkpoint\s+mutation"]
    for file_path in files:
        path = Path(file_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                matches.append({
                    "file": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
                    "line": text.count("\n", 0, match.start()) + 1,
                    "pattern": pattern,
                    "match": match.group(0),
                })
    return {
        "schema_version": "gis_recommend.workflow_usability.forbidden_pattern_scan.v1",
        "created_at": _now(),
        "files": [str(Path(path)) for path in files],
        "match_count": len(matches),
        "matches": matches,
        "status": "pass" if not matches else "fail",
        "result": "pass" if not matches else "fail",
    }


def evaluate_workflow_usability(
    *,
    data_path: Path,
    splits_path: Path,
    hierarchy_path: Path,
    id_mappings_path: Path,
    l3_vocab_path: Path,
    output_root: Path,
    eval_samples: int = 200,
    seed: int = 42,
) -> dict:
    random.seed(int(seed))

    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    train_idx = [int(i) for i in splits.get("train_indices", [])]
    test_idx = [int(i) for i in splits.get("test_indices", [])]
    selected = test_idx[:min(int(eval_samples), len(test_idx))]

    train_wfs = [workflows[i] for i in train_idx]
    evaluator = UsabilityEvaluator(
        hierarchy_path, id_mappings_path, l3_vocab_path, train_wfs,
    )
    retrieval = LexicalRetrieval(train_wfs)
    markov = MarkovBaseline(train_wfs)

    per_sample = []
    per_task: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    failure_counter: Counter = Counter()
    usable_ex: list[dict] = []
    unusable_ex: list[dict] = []

    for test_idx in selected:
        wf = workflows[int(test_idx)]
        task = _task_type(wf)
        ref_tokens = _content_tokens(wf.get("l3_sequence", []))

        # Retrieval candidates
        ret_cands = retrieval.retrieve(task, query_text=_task_text(wf), k=10)
        ret_usability = evaluate_topk(ret_cands, evaluator, task)

        # Markov candidates
        markov_seqs = markov.generate(k=5)
        markov_cands = [{"tokens": seq, "rank": i} for i, seq in enumerate(markov_seqs)]
        markov_usability = evaluate_topk(markov_cands, evaluator, task)

        # Reference usability
        ref_result = evaluator.evaluate(ref_tokens, task)

        # ---- Accumulate per-sample ----
        t1 = ret_usability["top1"]
        t1u = t1["per_candidate"][0] if t1["per_candidate"] else None

        sample_rec = {
            "test_index": test_idx,
            "task_type": task,
            "reference_length": len(ref_tokens),
            "reference_usability": {
                "required_step_coverage": ref_result.required_step_coverage,
                "harmful_step_rate": ref_result.harmful_step_rate,
                "executable_qgis_mapping_rate": ref_result.executable_qgis_mapping_rate,
                "workflow_logic_consistency": ref_result.workflow_logic_consistency,
                "redundancy_rate": ref_result.redundancy_rate,
                "usability_score": ref_result.usability_score,
                "usable": ref_result.usable,
            },
            "retrieval_candidates_found": len(ret_cands),
            "retrieval": ret_usability,
            "markov": markov_usability,
            "retrieval_top1_usable": t1u["usable"] if t1u else False,
            "retrieval_top1_score": t1u["usability_score"] if t1u else 0.0,
            "retrieval_top3_any_usable": ret_usability["top3"]["any_usable"],
            "retrieval_top5_any_usable": ret_usability["top5"]["any_usable"],
        }
        per_sample.append(sample_rec)

        # Per-task accumulation
        for kl in ["top1", "top3", "top5"]:
            rd = ret_usability[kl]
            for mk in ["any_usable", "usable_rate", "avg_usability_score", "best_usability_score"]:
                per_task[task][f"retrieval_{kl}_{mk}"].append(float(rd[mk]))

        # Failure taxonomy
        if t1u and not t1u["usable"]:
            for fp in t1u.get("forbidden_patterns", []):
                failure_counter[fp] += 1
            for lv in t1u.get("logic_violations", []):
                failure_counter[f"logic:{lv[:60]}"] += 1
            if t1u["executable_qgis_mapping_rate"] < 0.5:
                failure_counter["low_qgis_mapping"] += 1

        # Examples
        if t1u:
            ex = {
                "test_index": test_idx,
                "task_type": task,
                "candidate_tokens": t1u["tokens"],
                "reference_tokens": ref_tokens,
                "usability": {k: v for k, v in t1u.items() if k not in ("tokens",)},
            }
            if t1u["usable"] and len(usable_ex) < 10:
                usable_ex.append(ex)
            elif not t1u["usable"] and len(unusable_ex) < 10:
                unusable_ex.append(ex)

    # ---- Aggregate ----
    def _mean(vs):
        return sum(vs) / len(vs) if vs else 0.0

    t1_scores = [s["retrieval_top1_score"] for s in per_sample]
    t1_exec = [s["retrieval"]["top1"]["per_candidate"][0]["executable_qgis_mapping_rate"]
               for s in per_sample if s["retrieval"]["top1"]["per_candidate"]]
    t1_logic = [s["retrieval"]["top1"]["per_candidate"][0]["workflow_logic_consistency"]
                for s in per_sample if s["retrieval"]["top1"]["per_candidate"]]
    t1_cov = [s["retrieval"]["top1"]["per_candidate"][0]["required_step_coverage"]
              for s in per_sample if s["retrieval"]["top1"]["per_candidate"]]

    aggr = {
        "n_samples": len(per_sample),
        "top1_usable_rate": round(_mean([s["retrieval_top1_usable"] for s in per_sample]), 6),
        "top3_any_usable_rate": round(_mean([s["retrieval_top3_any_usable"] for s in per_sample]), 6),
        "top5_any_usable_rate": round(_mean([s["retrieval_top5_any_usable"] for s in per_sample]), 6),
        "mean_usability_score": round(_mean(t1_scores), 6),
        "mean_executable_qgis_mapping_rate": round(_mean(t1_exec), 6),
        "mean_workflow_logic_consistency": round(_mean(t1_logic), 6),
        "mean_required_step_coverage": round(_mean(t1_cov), 6),
        "reference_mean_usability_score": round(
            _mean([s["reference_usability"]["usability_score"] for s in per_sample]), 6,
        ),
        "bootstrap": {
            "usability_score": bootstrap_ci(t1_scores),
            "executable_qgis_mapping_rate": bootstrap_ci(t1_exec),
            "workflow_logic_consistency": bootstrap_ci(t1_logic),
            "required_step_coverage": bootstrap_ci(t1_cov),
        },
    }

    # Per-task breakdown
    per_task_rows = []
    for task in sorted(per_task):
        d = per_task[task]
        row = {"task_type": task}
        for mk in ["top1_usable_rate", "top1_avg_usability_score", "top1_best_usability_score",
                    "top3_any_usable", "top5_any_usable"]:
            k = f"retrieval_{mk}"
            row[k] = round(_mean(d.get(k, [])), 6)
        row["n_samples"] = len(d.get("retrieval_top1_usable_rate", []))
        per_task_rows.append(row)

    # Failure taxonomy
    failure_items = [{"category": c, "count": n} for c, n in failure_counter.most_common(40)]

    # Forbidden pattern definitions
    fp_defs = [
        ("FP01", "filter_after_compute", "Filter/clip appears after compute without commutative support", "high"),
        ("FP02", "export_before_processing", "Export/save appears before main processing", "critical"),
        ("FP03", "data_source_in_middle", "Data creation/loading in middle of workflow", "medium"),
        ("FP04", "consecutive_duplicate", "Same operator appears consecutively", "low"),
        ("FP05", "compute_without_source", "Compute without preceding data source or filter step", "high"),
        ("FP06", "raster_vector_mismatch_no_bridge", "Mixed raster/vector domains without bridge operator", "high"),
        ("FP08", "degenerate_workflow", "Workflow too short (<2) or too long (>50)", "medium"),
        ("FP09", "export_only", "Export is the only meaningful operation", "critical"),
    ]

    # Usability criteria
    usability_criteria = {
        "min_usability_score": 0.6,
        "min_executable_qgis_mapping_rate": 0.5,
        "blocked_critical_patterns": ["FP02", "FP05", "FP09"],
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "eval_samples": len(selected),
        "governance": {
            "evaluation_only": True,
            "no_training": True,
            "no_checkpoint_modification": True,
            "no_architecture_redesign": True,
            "no_semantic_retrieval": True,
            "no_ontology_expansion": True,
            "no_llm_judging": True,
            "no_execution_simulation": True,
            "rule_source": "strict token-level checks using classification hierarchy, QGIS mappings, and commutative pairs",
        },
        "aggregate_metrics": aggr,
        "usability_criteria": usability_criteria,
        "per_task_usability_breakdown": per_task_rows,
        "failure_taxonomy": failure_items,
        "forbidden_pattern_definitions": [
            {"id": pid, "name": pname, "description": pdesc, "severity": psev}
            for pid, pname, pdesc, psev in fp_defs
        ],
        "usable_workflow_examples": usable_ex,
        "unusable_workflow_examples": unusable_ex,
        "l3_qgis_coverage": {
            "total_l3_codes": len(evaluator.code_to_id),
            "l3_with_qgis": len([k for k, v in evaluator.token_has_qgis.items() if v]),
            "l3_without_qgis": len([k for k, v in evaluator.token_has_qgis.items() if not v]),
        },
        "commutative_pairs_count": len(evaluator.commutative_pairs),
    }

    # Write all artifacts
    output_root.mkdir(parents=True, exist_ok=True)

    _write_json(output_root / "workflow_usability_report.json", report)

    _write_json(output_root / "topk_usable_statistics.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "top1_usable_rate": aggr["top1_usable_rate"],
        "top3_any_usable_rate": aggr["top3_any_usable_rate"],
        "top5_any_usable_rate": aggr["top5_any_usable_rate"],
        "bootstrap": aggr["bootstrap"],
    })

    _write_json(output_root / "workflow_failure_taxonomy.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "failure_taxonomy": failure_items,
        "forbidden_patterns": [{"id": pid, "name": pn, "severity": ps} for pid, pn, _, ps in fp_defs],
    })

    _write_json(output_root / "usable_workflow_examples.json", {
        "schema_version": SCHEMA_VERSION,
        "count": len(usable_ex),
        "examples": usable_ex,
    })

    _write_json(output_root / "unusable_workflow_examples.json", {
        "schema_version": SCHEMA_VERSION,
        "count": len(unusable_ex),
        "examples": unusable_ex,
    })

    # CSV
    csv_path = output_root / "per_task_usability_breakdown.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task_type", "n_samples",
        "retrieval_top1_usable_rate", "retrieval_top1_avg_usability_score",
        "retrieval_top1_best_usability_score",
        "retrieval_top3_any_usable", "retrieval_top5_any_usable",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in per_task_rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    # Markdown summary
    md_lines = [
        "# Workflow Usability Evaluation",
        "",
        f"**Schema:** `{SCHEMA_VERSION}`",
        f"**Date:** {_now()}",
        f"**Samples evaluated:** {len(selected)}",
        "",
        "## Purpose",
        "",
        "Measure whether retrieval-centered workflow planning produces practically",
        "usable QGIS operator chains, even when sequence-level metrics (LCS/token accuracy)",
        "are low. ALL validation is strict rule-based — no LLM judging, no semantic",
        "equivalence, no execution simulation.",
        "",
        "## Aggregate Results (Retrieval Top-1)",
        "",
        "| Metric | Value | Bootstrap 95% CI |",
        "| --- | ---: | --- |",
        f"| Top-1 Usable Rate | {aggr['top1_usable_rate']:.4f} | — |",
        f"| Top-3 Any Usable | {aggr['top3_any_usable_rate']:.4f} | — |",
        f"| Top-5 Any Usable | {aggr['top5_any_usable_rate']:.4f} | — |",
        f"| Mean Usability Score | {aggr['mean_usability_score']:.4f} | [{aggr['bootstrap']['usability_score']['ci_lower']}, {aggr['bootstrap']['usability_score']['ci_upper']}] |",
        f"| Mean QGIS Mapping Rate | {aggr['mean_executable_qgis_mapping_rate']:.4f} | [{aggr['bootstrap']['executable_qgis_mapping_rate']['ci_lower']}, {aggr['bootstrap']['executable_qgis_mapping_rate']['ci_upper']}] |",
        f"| Mean Logic Consistency | {aggr['mean_workflow_logic_consistency']:.4f} | [{aggr['bootstrap']['workflow_logic_consistency']['ci_lower']}, {aggr['bootstrap']['workflow_logic_consistency']['ci_upper']}] |",
        f"| Mean Step Coverage | {aggr['mean_required_step_coverage']:.4f} | [{aggr['bootstrap']['required_step_coverage']['ci_lower']}, {aggr['bootstrap']['required_step_coverage']['ci_upper']}] |",
        f"| Reference Usability Score | {aggr['reference_mean_usability_score']:.4f} | — |",
        "",
        "## Usability Criteria",
        "",
        "A workflow is **usable** when:",
        f"- Usability score >= {usability_criteria['min_usability_score']}",
        f"- No critical forbidden patterns ({', '.join(usability_criteria['blocked_critical_patterns'])})",
        f"- QGIS mapping rate >= {usability_criteria['min_executable_qgis_mapping_rate']}",
        "",
        "## Metrics Definitions",
        "",
        "| Metric | Definition |",
        "| --- | --- |",
        "| **required_step_coverage** | Fraction of task-critical operators (>=30% of training samples for this task type) present in candidate |",
        "| **harmful_step_rate** | Fraction of operators violating basic GIS ordering (export first, orphan bridge, data source mid-workflow) |",
        "| **missing_critical_step_rate** | Fraction of task-critical operators absent from candidate |",
        "| **executable_qgis_mapping_rate** | Fraction of L3 tokens that map to >=1 QGIS operator in id_mappings_v2.json |",
        "| **workflow_logic_consistency** | Score 0-1 for GIS workflow ordering rules (compute before filter, export position, composite after filter, has compute step) |",
        "| **redundancy_rate** | Fraction of consecutive duplicate operator tokens |",
        "",
        "## Forbidden Patterns",
        "",
    ]
    for pid, pname, pdesc, psev in fp_defs:
        md_lines.append(f"- **{pid}** ({psev}): {pname} — {pdesc}")

    md_lines.extend([
        "",
        "## Top Failure Categories",
        "",
    ])
    for item in failure_items[:15]:
        md_lines.append(f"- **{item['category']}**: {item['count']} samples")

    md_lines.extend([
        "",
        "## QGIS Mapping Coverage",
        "",
        f"- {report['l3_qgis_coverage']['l3_with_qgis']}/{report['l3_qgis_coverage']['total_l3_codes']} L3 codes have QGIS operator mappings",
        f"- {report['commutative_pairs_count']} commutative operator pairs discovered",
        "",
        "## Interpretation Boundary",
        "",
        "- `required_step_coverage` uses training-data frequency as a proxy for criticality; not semantic necessity.",
        "- `executable_qgis_mapping_rate` only checks existence of >=1 QGIS mapping per token; not parameter compatibility.",
        "- `workflow_logic_consistency` uses L1/L2 category-based heuristics; not graph execution.",
        "- Usable != correct. A workflow passing all rules may still produce wrong output. A workflow failing rules may still be valid.",
        "- These metrics estimate PRACTICAL USABILITY, not sequence similarity.",
        "",
    ])

    (output_root / "workflow_usability_summary.md").write_text(
        "\n".join(md_lines), encoding="utf-8",
    )

    return report


# ===========================================================================
# CLI
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Evaluate workflow usability")
    parser.add_argument(
        "--data-path",
        default=str(ROOT / "outputs_v2/pipeline/step8_quality_gate"
                    / "labeled_workflows_l3_v4_quality_gate.json"),
    )
    parser.add_argument(
        "--splits-path",
        default=str(ROOT / "outputs_v2/pipeline/step8_quality_gate"
                    / "dataset_splits_v4_quality_gate.json"),
    )
    parser.add_argument(
        "--hierarchy-path",
        default=str(ROOT / "outputs_v2/classification_hierarchy_v2.csv"),
    )
    parser.add_argument(
        "--id-mappings-path",
        default=str(ROOT / "outputs_v2/id_mappings_v2.json"),
    )
    parser.add_argument(
        "--l3-vocab-path",
        default=str(ROOT / "outputs_v2/l3_vocab_v2.json"),
    )
    parser.add_argument(
        "--output-root",
        default=str(ROOT / "outputs_v2/v5_final_reports/workflow_usability_evaluation"),
    )
    parser.add_argument("--eval-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report = evaluate_workflow_usability(
        data_path=Path(args.data_path),
        splits_path=Path(args.splits_path),
        hierarchy_path=Path(args.hierarchy_path),
        id_mappings_path=Path(args.id_mappings_path),
        l3_vocab_path=Path(args.l3_vocab_path),
        output_root=Path(args.output_root),
        eval_samples=args.eval_samples,
        seed=args.seed,
    )

    print(f"Usability evaluation complete.")
    agg = report["aggregate_metrics"]
    print(f"  Samples: {report['eval_samples']}")
    print(f"  Top-1 usable rate: {agg['top1_usable_rate']:.4f}")
    print(f"  Top-3 any usable: {agg['top3_any_usable_rate']:.4f}")
    print(f"  Top-5 any usable: {agg['top5_any_usable_rate']:.4f}")
    print(f"  Mean usability score: {agg['mean_usability_score']:.4f}")
    print(f"  Mean QGIS mapping: {agg['mean_executable_qgis_mapping_rate']:.4f}")
    print(f"  Mean logic consistency: {agg['mean_workflow_logic_consistency']:.4f}")
    print(f"  Reports: {args.output_root}")


if __name__ == "__main__":
    main()
