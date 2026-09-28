"""Build a versioned GEE skip authority from a frozen parent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revise_skip_authority(
    *,
    input_path: Path,
    output_path: Path,
    version: str,
    remove_operators: Iterable[str],
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    raw_operators = payload.get("skip_operators")
    if not isinstance(raw_operators, list) or not all(
        isinstance(value, str) and value for value in raw_operators
    ):
        raise ValueError("parent authority has invalid skip_operators")

    operators = {value.casefold() for value in raw_operators}
    removals = {str(value).casefold() for value in remove_operators if str(value)}
    missing = sorted(removals - operators)
    if missing:
        raise ValueError(f"removal operators not present in parent authority: {missing}")
    if not version.strip():
        raise ValueError("version must be non-empty")

    revised = {
        "version": version,
        "skip_operators": sorted(operators - removals),
        "parent_authority": {
            "path": str(input_path),
            "sha256": _sha256(input_path),
            "version": payload.get("version"),
        },
        "changes": {"removed_operators": sorted(removals)},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(revised, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "output_path": str(output_path),
        "output_sha256": _sha256(output_path),
        "skip_operator_count": len(revised["skip_operators"]),
        "removed_operator_count": len(removals),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--remove", action="append", default=[], required=True)
    args = parser.parse_args()
    summary = revise_skip_authority(
        input_path=args.input,
        output_path=args.output,
        version=args.version,
        remove_operators=args.remove,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
