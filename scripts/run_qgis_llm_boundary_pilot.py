"""Run an isolated LLM boundary proposal pilot over a frozen API review packet.

The model proposes only source line spans and dependency edges.  The local
validator rejects lines and edges that are not present in the frozen AST-derived
steps.  No L3 labels or training rows are produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

MODEL = "deepseek-v4-flash-0731"
ENDPOINT = "https://tokenrhythm.studio/v1/chat/completions"
SCHEMA = "gis_recommend.qgis_llm_boundary_pilot.v3"
PROMPT_VERSION = "boundary_single_path_v3"

_CONTROL_RE = re.compile(r"(?m)^\s*(?:if|elif|else|for|while)\b")
_SINK_RE = re.compile(r"(?:\.addFeatures?|\.addFeature|writeAsVectorFormat(?:V2|V3)?)\s*\(")
_DATA_CALL_RE = re.compile(
    r"(?P<receiver>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\(\))*)\s*\.\s*"
    r"(?P<method>addFeatures?|setGeometry|setAttributes|updateFields|addAttributes|updateExtents)\s*\("
)
_CONTROL_PATH_RE = re.compile(r"^(?P<kind>if|elif|else|for|while|try|except|finally):(?P<line>\d+):")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prompt(row: dict[str, Any]) -> str:
    steps = [
        {
            "index": step.get("step_index"),
            "line_start": step.get("line_start"),
            "line_end": step.get("line_end"),
            "call_name": step.get("call_name"),
            "call_role": step.get("call_role"),
            "receiver": step.get("receiver"),
            "produced_names": step.get("produced_names", []),
            "consumed_names": step.get("consumed_names", []),
            "pattern_family": step.get("pattern_family"),
        }
        for step in row.get("steps", [])
    ]
    payload = {
        "source_sha256": row.get("source_sha256"),
        "lexical_scope": row.get("lexical_scope"),
        "pattern_names": row.get("pattern_names", []),
        "source_span": row.get("source_span"),
        "boundary_source": row.get("boundary_source", ""),
        "source_windows": row.get("source_windows", []),
        "steps": steps,
    }
    return (
        f"You are proposing a QGIS API local task boundary ({PROMPT_VERSION}). Return JSON only. "
        "Use only the supplied step indices and line numbers. Do not invent calls. "
        "Select one connected local unit on exactly one executable control-flow path when provable; otherwise abstain. "
        "Never chain sibling if/elif/else branches or alternative representations. "
        "Keep every source-visible guard that controls a selected transform. "
        "Do not treat one iteration of a for/while loop as the complete schema or output boundary; abstain if loop completeness cannot be proven. "
        "If sequential sink calls occur on the same path, abstain rather than silently dropping one. "
        "The boundary span must include every control_path header line for selected steps. "
        "Within the proposed span, every visible QGIS data call (addFeature(s), setGeometry, "
        "setAttributes, addAttributes, updateFields, updateExtents) must correspond to a supplied step; "
        "if a visible call is missing from the supplied steps, abstain. "
        "An empty selection is invalid; use abstain_reason and null span when no boundary is provable. "
        "A sink is a step whose call_role is sink_output. Output exactly: "
        "{unit_start_line:int|null, unit_end_line:int|null, selected_step_indices:[int], "
        "sink_step_indices:[int], dependency_edges:[{from_step:int,to_step:int,via_variable:str}], "
        "abstain_reason:string|null}.\nEVIDENCE:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def validate(output: Any, row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(output, dict):
        return None, ["response_not_object"]
    steps = {int(s["step_index"]): s for s in row.get("steps", []) if isinstance(s.get("step_index"), int)}
    selected = output.get("selected_step_indices")
    sinks = output.get("sink_step_indices")
    edges = output.get("dependency_edges")
    start = output.get("unit_start_line")
    end = output.get("unit_end_line")
    if not isinstance(selected, list) or not all(isinstance(x, int) and x in steps for x in selected):
        errors.append("invalid_selected_steps")
    if not isinstance(sinks, list) or not all(isinstance(x, int) and x in steps for x in sinks):
        errors.append("invalid_sink_steps")
    if isinstance(selected, list) and len(set(selected)) != len(selected):
        errors.append("duplicate_selected_steps")
    if isinstance(sinks, list) and len(set(sinks)) != len(sinks):
        errors.append("duplicate_sink_steps")
    if isinstance(selected, list) and not selected:
        errors.append("empty_selection")
    if isinstance(sinks, list) and len(sinks) != 1:
        errors.append("exactly_one_sink_required")
    if isinstance(selected, list) and isinstance(sinks, list) and sinks and sinks[0] not in selected:
        errors.append("sink_not_selected")
    if isinstance(sinks, list) and len(sinks) > 1:
        errors.append("multiple_sinks")
    selected_set = set(selected) if isinstance(selected, list) else set()
    if isinstance(edges, list):
        edge_keys: set[tuple[int, int, str]] = set()
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("from_step") not in steps or edge.get("to_step") not in steps:
                errors.append("invalid_dependency_edge")
                continue
            if not isinstance(edge.get("via_variable"), str) or not edge["via_variable"]:
                errors.append("missing_edge_variable")
                continue
            key = (edge["from_step"], edge["to_step"], edge["via_variable"])
            if key in edge_keys:
                errors.append("duplicate_dependency_edge")
            edge_keys.add(key)
            if edge["from_step"] not in selected_set or edge["to_step"] not in selected_set:
                errors.append("edge_endpoint_not_selected")
            if edge["from_step"] >= edge["to_step"]:
                errors.append("reverse_dependency_edge")
            from_step = steps[edge["from_step"]]
            to_step = steps[edge["to_step"]]
            variable = edge["via_variable"]
            if variable not in (from_step.get("produced_names") or []) or variable not in (to_step.get("consumed_names") or []):
                errors.append("unsupported_dataflow_edge")
    else:
        errors.append("invalid_dependency_edges")
    if isinstance(selected, list) and isinstance(sinks, list) and len(sinks) == 1 and selected:
        # Every selected node must belong to one connected component ending at the sink.
        adjacency: dict[int, set[int]] = {index: set() for index in selected}
        for edge in edges if isinstance(edges, list) else []:
            if isinstance(edge, dict) and edge.get("from_step") in adjacency and edge.get("to_step") in adjacency:
                adjacency[edge["from_step"]].add(edge["to_step"])
                adjacency[edge["to_step"]].add(edge["from_step"])
        seen = {sinks[0]}
        frontier = [sinks[0]]
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency.get(current, set()) - seen:
                seen.add(neighbor)
                frontier.append(neighbor)
        if seen != selected_set:
            errors.append("disconnected_selected_steps")

        if not isinstance(start, int) or not isinstance(end, int) or start > end:
            errors.append("invalid_boundary_span")
        else:
            text = _source_text(row)
            errors.extend(_semantic_source_checks(row, selected, text, start, end))
    if errors:
        return None, sorted(set(errors))
    if not isinstance(start, int) or not isinstance(end, int) or start > end:
        return None, ["invalid_boundary_span"]
    selected_lines = [line for index in selected for line in (steps[index].get("line_start"), steps[index].get("line_end"))]
    if any(not isinstance(line, int) or line < start or line > end for line in selected_lines):
        return None, ["boundary_span_does_not_cover_selected_steps"]
    return {
        "unit_start_line": start,
        "unit_end_line": end,
        "selected_step_indices": sorted(selected),
        "sink_step_indices": sorted(sinks),
        "dependency_edges": edges,
        "abstain_reason": output.get("abstain_reason"),
    }, []


def _source_text(row: dict[str, Any]) -> str:
    chunks = []
    boundary = row.get("boundary_source")
    if isinstance(boundary, str):
        chunks.append(boundary)
    for window in row.get("source_windows") or []:
        if isinstance(window, dict) and isinstance(window.get("text"), str):
            chunks.append(window["text"])
    return "\n".join(chunks)


def _semantic_source_checks(
    row: dict[str, Any],
    selected: list[int],
    source_text: str,
    boundary_start: int,
    boundary_end: int,
) -> list[str]:
    steps = {int(step["step_index"]): step for step in row.get("steps", []) if isinstance(step.get("step_index"), int)}
    errors: list[str] = []
    ordered = sorted((steps[index] for index in selected), key=lambda step: int(step.get("line_start", 0)))

    # A selected step under a control path is not self-contained unless the
    # controlling header is inside the proposed source span.
    for step in ordered:
        for path in step.get("control_path") or []:
            match = _CONTROL_PATH_RE.match(str(path))
            if match and not (boundary_start <= int(match.group("line")) <= boundary_end):
                errors.append("control_guard_outside_boundary")

    # The upstream extractor is authoritative for available steps.  If the
    # source span visibly contains another QGIS data mutation that is absent
    # from that step list, the LLM cannot safely repair the incomplete chain.
    represented = {
        re.sub(r"\(\)", "", str(steps[index].get("call_name") or "").replace(" ", ""))
        for index in selected
        if index in steps
    }
    for line_number, line in _source_lines(row):
        if not (boundary_start <= line_number <= boundary_end):
            continue
        code = line.split("#", 1)[0]
        for match in _DATA_CALL_RE.finditer(code):
            call_name = f"{match.group('receiver')}.{match.group('method')}"
            normalized_call = re.sub(r"\(\)", "", call_name.replace(" ", ""))
            if normalized_call not in represented:
                errors.append("unrepresented_qgis_data_call")
                break
    # Repeated same-call selections separated by branch syntax are sibling alternatives.
    for left, right in zip(ordered, ordered[1:]):
        if left.get("call_name") != right.get("call_name"):
            continue
        left_end = int(left.get("line_end", 0))
        right_start = int(right.get("line_start", 0))
        between = "\n".join(
            window.get("text", "")
            for window in row.get("source_windows", [])
            if isinstance(window, dict)
            and int(window.get("line_end", 0)) >= left_end
            and int(window.get("line_start", 0)) <= right_start
        )
        if _CONTROL_RE.search(between) and re.search(r"\b(?:elif|else)\b", between):
            errors.append("mutually_exclusive_branch_steps")
            break

    # An intersects guard is a required precondition for a selected intersection transform.
    if (
        re.search(r"\bintersects\s*\(", source_text)
        and any(".intersection" in str(step.get("call_name")) for step in ordered)
        and not any(".intersects" in str(step.get("call_name")) for step in ordered)
    ):
        errors.append("omitted_control_precondition")

    # A loop-local addAttribute followed by export is not a complete schema boundary.
    if (
        any("addAttribute" in str(step.get("call_name")) for step in ordered)
        and _CONTROL_RE.search(source_text)
        and re.search(r"(?m)^\s*for\b", source_text)
        and any(step.get("call_role") == "sink_output" for step in ordered)
    ):
        errors.append("loop_body_boundary_incomplete")

    # Two sink-like calls in one contiguous window are sequential output effects.
    for window in row.get("source_windows", []) or []:
        if not isinstance(window, dict) or not isinstance(window.get("text"), str):
            continue
        text = "\n".join(line.split("#", 1)[0] for line in window["text"].splitlines())
        if len(_SINK_RE.findall(text)) < 2:
            continue
        list_sink = re.search(r"\.addFeatures\s*\(\s*\[\s*([A-Za-z_]\w*)\s*\]\s*\)", text)
        if list_sink and re.search(rf"\.addFeature\s*\(\s*{re.escape(list_sink.group(1))}\s*\)", text):
            errors.append("sequential_multiple_sinks")
            break
    return errors


def _source_lines(row: dict[str, Any]) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    boundary = row.get("boundary_source")
    span = row.get("source_span")
    if isinstance(boundary, str) and isinstance(span, list) and len(span) == 2:
        start = int(span[0])
        lines.extend((start + offset, text) for offset, text in enumerate(boundary.splitlines()))
    for window in row.get("source_windows", []) or []:
        if not isinstance(window, dict) or not isinstance(window.get("text"), str):
            continue
        start = int(window.get("line_start", 0) or 0)
        lines.extend((start + offset, text) for offset, text in enumerate(window["text"].splitlines()))
    return lines


def call_model(api_key: str, message: str) -> dict[str, Any]:
    body = {"model": MODEL, "temperature": 0, "messages": [{"role": "user", "content": message}]}
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = "\n".join(content.splitlines()[1:-1]).strip()
    return json.loads(content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=Path)
    parser.add_argument("--calibration-review", type=Path)
    parser.add_argument("--holdout-review", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    if args.calibration_review or args.holdout_review:
        if not (args.calibration_review and args.holdout_review):
            raise ValueError("calibration and holdout must be supplied together")
        per_split = args.max_rows // 2
        calibration = load_jsonl(args.calibration_review)[:per_split]
        holdout = load_jsonl(args.holdout_review)[:per_split]
        for row in calibration:
            row["review_split"] = "calibration"
        for row in holdout:
            row["review_split"] = "holdout"
        rows = calibration + holdout
    elif args.review:
        rows = load_jsonl(args.review)[: args.max_rows]
    else:
        raise ValueError("supply --review or --calibration-review plus --holdout-review")
    if len(rows) != args.max_rows:
        raise ValueError(f"expected {args.max_rows} review rows, got {len(rows)}")
    shas = [str(row.get("source_sha256")) for row in rows]
    if len(set(shas)) != len(shas):
        raise ValueError("source_sha256 overlap inside pilot")
    api_key = os.environ.get("TOKENRHYTHM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not args.dry_run and not api_key:
        raise RuntimeError("set TOKENRHYTHM_API_KEY or DEEPSEEK_API_KEY")
    def process(row: dict[str, Any]) -> dict[str, Any]:
        base = {
            "schema": SCHEMA,
            "model": MODEL,
            "source_sha256": row.get("source_sha256"),
            "record_id": row.get("record_id"),
            "review_split": row.get("review_split"),
            "input_sha256": hashlib.sha256(prompt(row).encode()).hexdigest(),
            "training_rows_emitted": 0,
            "training_admission": "not_granted_llm_boundary_pilot",
        }
        if args.dry_run:
            return {**base, "status": "staged", "prompt": prompt(row)}
        try:
            proposal = call_model(api_key, prompt(row))
            validated, errors = validate(proposal, row)
            return {**base, "status": "validated_candidate" if validated else "deferred_invalid_proposal", "proposal": validated, "validation_errors": errors}
        except Exception as exc:  # noqa: BLE001  # fail closed per source
            return {**base, "status": "deferred_request_failure", "reason": type(exc).__name__}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        output_rows = list(executor.map(process, rows))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "llm_boundary_ledger_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows), encoding="utf-8")
    summary = {
        "schema": f"{SCHEMA}.summary",
        "model": MODEL,
        "rows": len(output_rows),
        "source_sha_unique": len(set(shas)),
        "split_counts": {split: sum(row.get("review_split") == split for row in rows) for split in sorted({row.get("review_split") for row in rows})},
        "status_counts": {status: sum(row["status"] == status for row in output_rows) for status in sorted({row["status"] for row in output_rows})},
        "training_rows_emitted": 0,
        "training_admission": "not_granted_llm_boundary_pilot",
    }
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
