# Turnkey dual-review dispatch for the 24 recovered DAGs (v0.2).
# Run from the benchmark worktree root after the agentrouter.org budget
# pool is restored. Produces reviewer_a_output.jsonl / reviewer_b_output.jsonl.
param(
    [string]$ReviewerAId = "codex-qgis-recovered-reviewer-a-20260910",
    [string]$ReviewerBId = "codex-qgis-recovered-reviewer-b-20260910"
)
$ErrorActionPreference = "Stop"
$brief = "benchmarks/qgis_planner_v1/authority/review_dispatch/v02_recovered_dag_review_brief_v1.md"
$outDir = "benchmarks/qgis_planner_v1/authority/review_dispatch"

foreach ($rid in @($ReviewerAId, $ReviewerBId)) {
    $suffix = if ($rid -match "-a-") { "a" } else { "b" }
    Write-Output "=== dispatching reviewer $rid ==="
    codex exec -s read-only --skip-git-repo-check -C (Get-Location).Path `
        "You are reviewer $rid, an independent QGIS graph reviewer. Read the brief at $brief and follow it exactly. Your reviewer_id is $rid. Review all 24 entries in the packet and output EXACTLY 24 JSON lines per the brief's output format, nothing else." `
        2>&1 | Tee-Object -FilePath "$outDir\reviewer_${suffix}_raw_output.txt"
}
Write-Output "Done. Raw outputs in $outDir. Ingest next: parse the last 24 JSON lines of each raw output into the review ledger."
