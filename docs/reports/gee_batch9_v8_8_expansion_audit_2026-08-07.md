# GEE Batch9 v8.8 Frozen Expansion Audit

## Result

The hash-bound 50-row full-source audit recomputed and matched all source SHA256
values from read-only `/home/yll/GEE/Data`.

| Metric | Value |
| --- | ---: |
| Pass | 43 |
| Critical fail | 7 |
| Defer | 0 |
| Point precision | 0.86 |
| Wilson 95% lower | 0.7381380628941446 |
| Decision | `failed_rule_repair_required` |

The evaluator emitted zero training rows. Train-only, validation/test, and production
admission remain closed. The evaluation summary SHA256 is
`3f1c95a1166e4bad25cbf9da3e80088290b798ac7d2683730f9ae53f2f55ca6f`.

## Findings

Five independent critical failures (`27`, `30`, `33`, `41`, and `44`) establish one
systematic gap: an output-relevant EE value is reassigned or accumulated in control
flow, but the slice retains only a terminal operation. The allowed repair is a
fail-closed gate for loop-carried reassignment, collection mutation, dynamic asset
enumeration, and multiple control-flow reaching writes without statically provable
lineage.

Two singleton failures remain separately recorded: `16` included an unreachable
callback statement after unconditional `return`, and `11` uses literal 1910 date
ranges outside all three Landsat input catalog coverages. Neither permits a rule
relaxation or admission of the 197 proposals.

## Next Gate

Apply only the proven control-flow lineage repair, replay Batch9 from AST/DAG through
proposal in independent A/B runs, then generate a new source-disjoint audit packet.
Do not repair individual records or admit current proposals.
