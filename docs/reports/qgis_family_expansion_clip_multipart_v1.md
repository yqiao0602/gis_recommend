# QGIS family expansion — clip -> multipart-to-singleparts

The calibrated contiguous-subsequence rule was applied to the full normalized
ledger. Among all 1,236 `processing_workflow` candidates (including
Processing-shaped assets found in either manifest pool), seven parent sources
matched `native:clip|qgis:multiparttosingleparts` and produced seven family
candidates. All seven source SHAs are verified; there are no multiple matched
spans and only one distinct full parent operator sequence.

The expanded records preserve the complete parent sequence, matched span,
`parent_source_sha256`, and candidate-only status. No source was sliced into a
new independent workflow and no L3 or task labels were invented.

Server output:
`/home/qy/system_redesign/diagnostics/qgis_family_expansion_clip_multipart_v1/`
