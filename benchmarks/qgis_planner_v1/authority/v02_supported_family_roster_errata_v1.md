# v0.2 Supported Family Roster Errata v1

Date: 2026-09-10

The frozen machine-readable roster remains authoritative and unchanged:
`v02_supported_family_roster.json` at commit `f186d31`.

The prose companion contains one identifier typo in its Tier-A list:
`L3_02_22_06` should be read as `L3_02_02_06` (Clip). The JSON authority and
`candidate_supply_summary.json` both use `L3_02_02_06`. This erratum does not
modify or re-hash the frozen roster; all downstream tooling must resolve the
identifier from the JSON authority.
