#!/usr/bin/env python3
"""Bootstrap unchanged upstream pipeline outputs into an outputs_v2 baseline.

Steps 1-5 are mapping-independent workflow extraction/normalization stages.
When the raw Workflowoutput* source tree is not available locally, this script
copies the previously generated step1-5 artifacts from ``outputs/pipeline`` into
``outputs_v2/pipeline`` so the full step1-8 quality audit can run against one
coherent baseline directory.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STEP_FILES = {
    1: "raw_workflows.json",
    2: "cleaned_workflows.json",
    3: "final_workflows.json",
    4: "standardized_workflows.json",
    5: "workflow_sequences.json",
}


def file_info(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy mapping-independent step1-5 outputs into outputs_v2 for full-chain audit."
    )
    parser.add_argument("--source-outputs-dir", default="outputs",
                        help="Source outputs root containing pipeline/step1-5.")
    parser.add_argument("--target-outputs-dir", default="outputs_v2",
                        help="Target outputs root to receive pipeline/step1-5.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing target step files.")
    args = parser.parse_args()

    source_root = (ROOT / args.source_outputs_dir).resolve()
    target_root = (ROOT / args.target_outputs_dir).resolve()
    copied = []
    skipped = []

    for step, filename in STEP_FILES.items():
        src = source_root / "pipeline" / f"step{step}" / filename
        dst = target_root / "pipeline" / f"step{step}" / filename
        if not src.exists():
            raise FileNotFoundError(f"Missing source step{step}: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not args.overwrite:
            skipped.append({"step": step, "reason": "target_exists", "target": file_info(dst)})
            continue
        shutil.copy2(src, dst)
        copied.append({"step": step, "source": file_info(src), "target": file_info(dst)})

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Bootstrap mapping-independent step1-5 artifacts into the v2 baseline for step1-8 audit.",
        "source_outputs_dir": str(source_root.relative_to(ROOT)),
        "target_outputs_dir": str(target_root.relative_to(ROOT)),
        "copied": copied,
        "skipped": skipped,
        "note": "Step1-5 do not use L3 mappings; v2 mapping changes start at step6.",
    }
    manifest_path = target_root / "pipeline" / "bootstrap_upstream_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Copied {len(copied)} files, skipped {len(skipped)} files")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
