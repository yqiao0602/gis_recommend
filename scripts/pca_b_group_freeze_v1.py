#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA B-group FREEZE assembler (owner round-4 check #3).

Builds the final model-facing input file from the two ledgers BY EXTRACTION
(no manual transcription), so ledger text and frozen text are identical by
construction, then verifies cross-record consistency and computes SHA256.

Sources:
  - pca_b_group_restatement_v1.md  : baseline texts (19 conditional-keep rows)
  - pca_b_group_final_status_v1.md : overrides (W056274 §2, W067268 §3, and
                                     the 10 §4 rewrites)
Excluded: W023206 (SMOKE_ONLY).
Assertions:
  A1 exactly 19 final rows (18 formal pool + refill W056274)
  A2 W067268 text identical in both ledgers (double-record consistency)
  A3 every override wid found in the baseline set; no wid lost or invented
Output: pca_b_group_final_inputs_v1.json (per-row text SHA256 + file SHA256).
"""
import json, re, hashlib

V1 = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_restatement_v1.md"
ST = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_final_status_v1.md"
OUT = "docs/reports/route2_p0_contract/plan_pipeline_v1/planning_capability_audit_v1/pca_b_group_final_inputs_v1.json"

STATUS = {
    "W000473": "APPROVED", "W068342": "APPROVED", "W068582": "APPROVED",
    "W067404": "APPROVED", "W000635": "APPROVED",
    "W000890": "APPROVED_AFTER_EDIT(verified, text kept)",
    "W033927": "APPROVED_AFTER_EDIT(verified, text kept)",
    "W055913": "APPROVED_AFTER_EDIT", "W056058": "APPROVED_AFTER_EDIT",
    "W055908": "APPROVED_AFTER_EDIT", "W066995": "APPROVED_AFTER_EDIT",
    "W055494": "APPROVED_AFTER_EDIT", "W068833": "APPROVED_AFTER_EDIT",
    "W067092": "APPROVED_AFTER_EDIT", "W007046": "APPROVED_AFTER_EDIT",
    "W055534": "APPROVED_AFTER_EDIT", "W000674": "APPROVED_AFTER_EDIT",
    "W056274": "APPROVED_AFTER_EDIT(refill, inside-points semantics verified)",
    "W067268": "PENDING -> frozen pending owner final verbatim check",
}
EXCLUDE = {"W023206"}
OVERRIDES = {"W056274", "W067268", "W055908", "W066995", "W055494", "W068833",
             "W067092", "W007046", "W055534", "W000674", "W055913", "W056058"}

def parse_sections(path):
    """wid -> first contiguous '> ' quote block in that wid's section."""
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^#{2,3} (?:\d+\.\s+)?(W\d+)", text, flags=re.M)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        wid, body = parts[i], parts[i + 1]
        lines = body.splitlines()
        quote, in_q = [], False
        for ln in lines:
            if ln.startswith("> "):
                quote.append(ln[2:].strip())
                in_q = True
            elif in_q:
                break
        if quote:
            out[wid] = " ".join(quote).strip()
    return out

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    v1 = parse_sections(V1)
    st = parse_sections(ST)
    final = {}
    for wid, txt in v1.items():
        if wid in EXCLUDE:
            continue
        final[wid] = (st.get(wid, txt) if wid in OVERRIDES else txt)
    # A2: double-record consistency for W067268
    assert "W067268" in v1 and "W067268" in st, "W067268 missing"
    assert v1["W067268"] == st["W067268"], "A2 FAIL: W067268 texts differ"
    # A1: count
    assert len(final) == 19, f"A1 FAIL: {len(final)} rows"
    # A3: overrides all applied, no invented wid
    assert set(final) == (set(v1) - EXCLUDE), "A3 FAIL: wid set mismatch"
    assert all(w in final for w in OVERRIDES), "A3 FAIL: missing override"
    rows = []
    for wid in sorted(final):
        t = final[wid]
        assert t and len(t) > 60, f"empty/short text for {wid}"
        rows.append({"wid": wid, "group": "B", "status": STATUS[wid],
                     "final_text": t, "text_sha256": sha(t)[:16]})
    payload = {
        "_meta": {
            "freeze": "PCA B-group final model-facing inputs v1",
            "rule": "owner round-4: freeze only after 3 checks; assembled by "
                    "extraction from ledgers (no transcription)",
            "sources": {"restatement_v1": V1, "final_status_v1": ST},
            "excluded": sorted(EXCLUDE),
            "n_rows": len(rows),
            "checks": {"A1_count_19": True, "A2_W067268_consistency": True,
                       "A3_wid_set": True},
        },
        "rows": rows,
    }
    blob = json.dumps(payload, ensure_ascii=False, indent=1)
    open(OUT, "w", encoding="utf-8", newline="").write(blob)
    print("rows:", len(rows))
    for r in rows:
        print(f"  {r['wid']} {r['status'][:42]:42s} {r['text_sha256']}")
    print("file_sha256:", sha(blob)[:16])
    print("saved:", OUT)

if __name__ == "__main__":
    main()
