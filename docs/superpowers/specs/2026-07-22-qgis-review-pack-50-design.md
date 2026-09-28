# QGIS Dedup-Aware 50-Row Review Pack Design

## Goal

Freeze a deterministic, human-reviewable 50-row package from
`pilot_v3_region_dedup_v1` without generating descriptions, admitting training
rows, or modifying `/home/yll`.

## Selection Contract

The package contains 50 unique region records in three ordered strata:

1. `high_evidence_representative` (18): one semantic representative for every
   stable-94 `complete_exact` and dependency `connected` signature.
2. `within_cluster_control` (12): nonrepresentative members paired with their
   semantic representatives. Prefer one control from each cluster whose strict
   AST differs from its representative; use high-evidence membership and cluster
   size only as later tie breaks. This directly tests semantic over-merging
   instead of spending the quota on byte/AST mirrors.
3. `diversity_representative` (20): remaining semantic representatives selected
   greedily to broaden source root, chain length, operator family, repeated-call
   state, stable-94 status, dependency status, source role, and risk flags. A
   semantic signature already covered by a control is not selected again here.

All tie breaks use source identity, owner line, and record ID so repeated builds
are byte-identical.

## Review Surface

`manual_review_50.csv` contains one row per selected record. It embeds:

- selection stratum and rationale;
- provenance, owner, operator chain, stable-94 mapping, parameter keys, and
  dependency edges;
- exact-AST and semantic-cluster membership;
- a deterministic comparison record, whether its AST is identical, shared
  semantic evidence, differing provenance/owner/AST evidence, and its source
  snippet;
- the selected record's complete owner/module snippet with line numbers;
- blank human fields for workflow boundary, operator identity/order, dependency,
  repeated-call meaning, stable-94 mapping, cluster validity, task completeness,
  description readiness, training-candidate readiness, notes, reviewer, and time.

Multiline snippets remain quoted CSV fields. The build also emits
`selection.jsonl`, `summary.json`, and `hash_ledger.json` for machine checks.

## Source Recovery

The input manifest supplies the nine named source roots. Each selected source is
resolved below its declared root, rehashed against `source_provenance`, decoded as
UTF-8 with optional BOM, and parsed with `ast`. Function/method records use the
recorded owner definition location; module records include the minimal line span
covering their selected Processing callsites. Snippets include one context line
on either side without reading unrelated files.

## Safety And Admission

- Validate the immutable dedup ledger before selecting rows.
- Require exactly 234 valid fingerprint rows and exactly `18+12+20` output rows.
- Keep semantic clusters as review evidence only.
- Keep taxonomy and training admission `not_granted`; emit zero training rows.
- Publish atomically only below an allowed `/home/qy` write root.
- Never write to `/home/yll` and never call an LLM.

## Verification

Unit tests cover quota selection, deterministic diversity, cluster pairing,
snippet extraction, blank human fields, input drift rejection, and byte-stable
artifacts. The server run independently checks row uniqueness, stratum counts,
all blank review fields, source hashes, artifact hashes, and a second byte-identical
build.
