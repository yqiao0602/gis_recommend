"""dx_state: workflow state manager for the DX pipeline (V1, minimal).

Scope (owner spec V1.0, implementation steps 1-4 / Phase A only):
state model, SQLite store, artifact registry, dependency invalidation,
issue import from existing evidence, and compatible ingestion of the
dx50_full_v1 tree. Recovery routing/execution and delivery gating are
later increments and deliberately absent here.

Authority split (frozen):
- stage files on disk  -> content and evidence authority (never overwritten)
- SQLite               -> current state, versions, dependencies, issues
- workflow_state.json  -> derived human-readable snapshot (not authoritative)

The code lives at the repository root instead of inside the data tree:
the tree sits under docs/reports/ where path length already exceeds the
Windows MAX_PATH limit for deep artifacts.
"""

__version__ = "0.1.0"
