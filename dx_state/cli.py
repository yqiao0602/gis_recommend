"""Command-line interface: init / import / reconcile / show / snapshot.

Examples (from the repository root):
  python -m dx_state.cli import    --tree <dx50_full_v1>
  python -m dx_state.cli reconcile --tree <dx50_full_v1>
  python -m dx_state.cli show      --tree <dx50_full_v1> --task PCA2-T-009
  python -m dx_state.cli snapshot  --tree <dx50_full_v1>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dx_state import ingest_dx50
from dx_state.snapshot import write_rebuild_report, write_run_snapshot
from dx_state.state_store import StateStore


def _store(tree: Path) -> StateStore:
    store = StateStore(tree / "state_db.sqlite")
    store.init_schema()
    return store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dx_state",
        description="Workflow state manager for the DX pipeline. "
                    "--tree is given after the subcommand.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--tree", required=True, type=Path,
                        help="dx50_full_v1-style tree root")
    sub.add_parser("init", parents=[common])
    sub.add_parser("import", parents=[common])
    sub.add_parser("reconcile", parents=[common])
    show = sub.add_parser("show", parents=[common])
    show.add_argument("--task", required=True)
    sub.add_parser("snapshot", parents=[common])
    args = parser.parse_args(argv)

    store = _store(args.tree)
    try:
        if args.cmd == "init":
            print(f"schema ready: {args.tree / 'state_db.sqlite'}")
        elif args.cmd == "import":
            report = ingest_dx50.import_tree(args.tree, store)
            report["rebuild_report"] = str(write_rebuild_report(args.tree, store))
            print(json.dumps(report, ensure_ascii=False, indent=1))
        elif args.cmd == "reconcile":
            print(json.dumps(
                ingest_dx50.reconcile_artifacts(args.tree, store),
                ensure_ascii=False, indent=1))
        elif args.cmd == "show":
            run_id = ingest_dx50.run_id_for(args.task)
            run = store.get_run(run_id)
            if run is None:
                print(f"unknown task: {args.task}")
                return 1
            state = {
                "run": dict(run),
                "steps": [dict(r) for r in store._conn.execute(
                    "SELECT step_no, name, step_status FROM steps"
                    " WHERE run_id = ? ORDER BY step_no", (run_id,))],
                "active_artifacts": [dict(r) for r in
                                     store.active_artifacts(run_id)],
                "issues": [dict(r) for r in store.issues(run_id)],
            }
            print(json.dumps(state, ensure_ascii=False, indent=1))
        elif args.cmd == "snapshot":
            paths = []
            for run_id in store.list_runs():
                paths.append(str(write_run_snapshot(args.tree, store, run_id)))
            print(json.dumps({"snapshots": len(paths)}, ensure_ascii=False))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
