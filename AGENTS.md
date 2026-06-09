# Project Operating Instructions

## Durable Context Protocol

This repository maintains project memory in Markdown. Do not leave important project context only in chat history.

At the start of any non-trivial session:

- Read `docs/PROJECT_CONTEXT.md`.
- If the user is working in Chinese or asks for human-facing context, also read `docs/PROJECT_CONTEXT.zh-CN.md`.
- Treat these documents as the current handoff source of truth unless local files or fresh verification prove otherwise.

After any meaningful phase of work, update the context documents without waiting for the user to ask:

- Record completed work, unfinished work, current blockers, and next actions.
- Record key decisions, changed files, why they changed, verification commands, and pitfalls that should not be repeated.
- Keep updates concise and durable. Do not paste raw chat transcripts.
- Keep the English and Chinese context documents substantively aligned.

Current context files:

- `docs/PROJECT_CONTEXT.md`: canonical technical handoff.
- `docs/PROJECT_CONTEXT.zh-CN.md`: Chinese human-facing mirror.

## Project-Specific Guardrails

- Default active data root is `outputs_v2` with the repaired 94-L3 mapping system.
- Keep `outputs/` as legacy 350-L3 compatibility unless explicitly migrating old scripts.
- Do not modify large data files under `outputs/` or `outputs_v2/` unless the task explicitly requires data regeneration.
- Do not rerun training unless the user explicitly requests it.
- Verify before reporting completion.

