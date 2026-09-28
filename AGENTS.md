# Project Operating Instructions

## Durable Context Protocol

This repository maintains project memory in Markdown. Do not leave important project context only in chat history.

At the start of any non-trivial session:

- Read `docs/CURRENT_STATE.md` first; it is the short, current handoff used for routine work.
- Read the full `docs/PROJECT_CONTEXT.md` only when the task needs historical evidence, detailed experiment provenance, or unresolved context not covered by `CURRENT_STATE.md`.
- If the user is working in Chinese or asks for human-facing context, read `docs/CURRENT_STATE.zh-CN.md` first; read the full `docs/PROJECT_CONTEXT.zh-CN.md` when detailed historical context is needed.
- For GEE data-processing work, then read `docs/GEE_CURRENT_STATE.md` (or `docs/GEE_CURRENT_STATE.zh-CN.md`) and treat it as the current GEE authority. Read `docs/GEE_PROJECT_CONTEXT.md` (or its Chinese mirror) when detailed GEE provenance is needed.
- GEE agents update only the GEE-specific context files and the GEE section of `task_plan.md`. They must not rewrite QGIS or benchmark state in the shared context files.
- Treat these documents as the current handoff source of truth unless local files or fresh verification prove otherwise.

After any meaningful phase of work, update project memory without waiting for the user to ask. Use the following file roles instead of copying the same text into every document:

- Record completed work, unfinished work, current blockers, and next actions.
- Record key decisions, changed files, why they changed, verification commands, and pitfalls that should not be repeated.
- Keep updates concise and durable. Do not paste raw chat transcripts.
- Keep the English and Chinese context documents substantively aligned.

Write-back rules:

- `docs/CURRENT_STATE.md` and `docs/CURRENT_STATE.zh-CN.md`: update after every meaningful phase. Keep only the current mainline, latest verified state, blockers, and immediate next actions. Replace stale state instead of accumulating a long history.
- `docs/PROJECT_CONTEXT.md` and `docs/PROJECT_CONTEXT.zh-CN.md`: update after meaningful technical or research progress. Record durable technical detail, decisions, changed files, verification evidence, remaining risks, and pitfalls. Keep both versions substantively aligned.
- `docs/GEE_CURRENT_STATE.md` and `docs/GEE_CURRENT_STATE.zh-CN.md`: GEE-only short handoff. Update after every meaningful GEE phase and replace stale GEE state instead of accumulating history.
- `docs/GEE_PROJECT_CONTEXT.md` and `docs/GEE_PROJECT_CONTEXT.zh-CN.md`: GEE-only durable technical evidence. Keep both versions substantively aligned.
- `progress.md`: append only when a project milestone, dataset gate, completed experiment, measured result, or substantial implementation phase is reached. It is the chronological factual log, not a copy of the current-state summary.
- `task_plan.md`: update only when task status, priority, execution order, blockers, acceptance gates, or the next-stage plan changes. It is the active plan, not a progress diary.
- Small read-only checks, minor wording fixes, and trivial edits do not require updates to all memory files. Update only the files whose role is materially affected.
- For a major phase completion, review all six files, but write only role-appropriate information to each one.

Current context files:

- `docs/CURRENT_STATE.md`: short English current-state entrypoint for routine sessions.
- `docs/CURRENT_STATE.zh-CN.md`: short Chinese current-state entrypoint.
- `docs/PROJECT_CONTEXT.md`: canonical technical handoff.
- `docs/PROJECT_CONTEXT.zh-CN.md`: Chinese human-facing mirror.
- `docs/GEE_CURRENT_STATE.md`: short English GEE data-processing entrypoint.
- `docs/GEE_CURRENT_STATE.zh-CN.md`: short Chinese GEE data-processing entrypoint.
- `docs/GEE_PROJECT_CONTEXT.md`: canonical GEE technical handoff.
- `docs/GEE_PROJECT_CONTEXT.zh-CN.md`: Chinese GEE technical handoff.
- `progress.md`: chronological milestone and verified-result log.
- `task_plan.md`: active priorities, gates, blockers, and next-step plan.

## Context Hygiene Protocol

Keep project memory layered instead of cumulative:

- Treat `docs/CURRENT_STATE.md` and `docs/CURRENT_STATE.zh-CN.md` as the only routine onboarding entrypoints. They should stay short enough to scan quickly and contain only the current mainline, active gates, current blockers, immediate next actions, and hard prohibitions.
- Do not append historical experiment detail, obsolete plans, long report summaries, or superseded conclusions to `CURRENT_STATE`. Replace stale text with the newest current conclusion and a link to the authoritative report or context section.
- Treat `docs/PROJECT_CONTEXT.md` and `docs/PROJECT_CONTEXT.zh-CN.md` as historical evidence stores. Older sections may be useful for provenance, but they are not current authority unless `CURRENT_STATE` or the latest local verification points to them.
- Treat `progress.md` as an append-only milestone log. It may contain old "current" wording from the date of an entry; do not use it as today's plan or state.
- Treat `task_plan.md` as the active plan only. Remove or demote completed/superseded plans instead of accumulating multiple "current stage" sections.
- If the same fact appears in three or more memory files, keep the detailed version in one authority location and replace the other copies with a short conclusion plus path.
- Mark stale-but-retained material as `superseded`, `archived`, `frozen`, or `not_granted` when deletion would lose useful provenance.

Cleanup triggers:

- After a meaningful phase completes, update `CURRENT_STATE` by compression, not accumulation.
- When a formal report exists under `docs/reports/`, keep only the decision, admission status, verification summary, and report path in current-state documents.
- When a plan is completed, blocked, or replaced, update `task_plan.md` so only live priorities remain.
- Before ending a non-trivial documentation or data-authority session, check whether the files touched introduced duplicate or stale onboarding context and clean it immediately.

## Project-Specific Guardrails

- Default active data root is `outputs_v2` with the repaired 94-L3 mapping system.
- Keep `outputs/` as legacy 350-L3 compatibility unless explicitly migrating old scripts.
- Do not modify large data files under `outputs/` or `outputs_v2/` unless the task explicitly requires data regeneration.
- Do not rerun training unless the user explicitly requests it.
- Verify before reporting completion.
