"""
analyze_l3_coverage_gaps.py

Systematic L3 code coverage gap analysis.
Cross-references semantic QGIS mappings × training data token frequencies
to find ALL under-covered L3 codes, not just the ones we stumble upon.

Output:
  outputs_v2/diagnostics/l3_coverage_gap_report.json   — machine-readable
  outputs_v2/diagnostics/l3_coverage_gap_report.md     — human-readable

Risk dimensions:
  1. Training coverage:  does this L3 code appear in training data?
  2. QGIS operator map:  are there QGIS operators semantically mapped to this code?
  3. Semantic strength:  how strong is the semantic similarity?
  4. Vector relevance:   is this a vector-analysis code (L3_02)?

Gap classification:
  - DATA_GAP:       has QGIS operators but ZERO training samples → mine scripts!
  - MAPPING_GAP:    no QGIS operators mapped → need crosswalk expansion
  - BOTH_GAP:       neither training data nor QGIS mappings
  - LOW_COVERAGE:   has some training but below threshold
  - ADEQUATE:       sufficient coverage in both dimensions
"""

import json
import csv
import sys
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Paths ───────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs_v2" / "diagnostics"
SEMANTIC_SCORES_PATH = PROJECT_ROOT / "outputs" / "l3_qgis_semantic_scores.json"
HIERARCHY_PATH = PROJECT_ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"

# Server training data path
SERVER_TRAINING_PATH = (
    "/home/qy/system_redesign/outputs_v2/pipeline/"
    "step8_quality_gate_qgis_vector_oversampled/"
    "labeled_workflows_l3_v4_quality_gate_qgis_vector_oversampled.json"
)
SERVER_SPLITS_PATH = (
    "/home/qy/system_redesign/outputs_v2/pipeline/"
    "step8_quality_gate_qgis_vector_oversampled/"
    "dataset_splits_v4_quality_gate_qgis_vector_oversampled.json"
)

# ── Risk thresholds ─────────────────────────────────────────────
MIN_TRAINING_SAMPLES = 50       # below this = low coverage
CRITICAL_TRAINING_SAMPLES = 0   # exactly 0 = critical gap
MIN_QGIS_OPERATORS = 2          # below this = mapping gap
MIN_SEMANTIC_SCORE = 0.35       # below this = weak semantic match


@dataclass
class L3CoverageInfo:
    """Coverage information for a single L3 code."""
    l3_code: str
    l3_name: str
    l3_description: str
    l2_code: str
    l2_name: str
    l1_code: str
    l1_name: str
    freq_v2: int  # historical frequency

    # Training data coverage
    training_sample_count: int = 0
    training_token_freq: int = 0
    total_train_samples: int = 0

    # QGIS semantic coverage
    qgis_mapped_count: int = 0       # explicitly mapped (crosswalk)
    qgis_discovered_count: int = 0   # discovered only (no crosswalk)
    max_semantic_score: float = 0.0
    top_qgis_operators: List[dict] = field(default_factory=list)

    # Computed
    gap_type: str = ""
    risk_score: float = 0.0
    is_vector: bool = False

    @property
    def training_pct(self) -> float:
        if self.total_train_samples == 0:
            return 0.0
        return 100.0 * self.training_sample_count / self.total_train_samples

    @property
    def total_qgis_ops(self) -> int:
        return self.qgis_mapped_count + self.qgis_discovered_count


def load_hierarchy(path: Path) -> Dict[str, dict]:
    """Load L3 classification hierarchy CSV → {l3_code: {name, desc, l2, l1, ...}}"""
    hierarchy = {}
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            code = row.get('l3_code', '').strip()
            if not code:
                continue
            hierarchy[code] = {
                'l3_name': row.get('l3_name', '').strip(),
                'l3_description': row.get('l3_description', '').strip(),
                'l2_code': row.get('l2_code', '').strip(),
                'l2_name': row.get('l2_name', '').strip(),
                'l1_code': row.get('l1_code', '').strip(),
                'l1_name': row.get('l1_name', '').strip(),
                'freq_v2': int(row.get('freq_v2', 0) or 0),
            }
    return hierarchy


def load_semantic_scores(path: Path) -> Tuple[dict, dict]:
    """Load L3→QGIS semantic scores.
    Returns (mapped_scores, discovered_mappings)
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('scores', {}), data.get('discovered_mappings', {})


def fetch_training_frequencies(
    host: str = "10.191.2.38",
    user: str = "qy",
    password: str = "@qy123456",
    cache_path: Optional[Path] = None,
) -> Tuple[Counter, Counter, int]:
    """Fetch training data from server and compute L3 token frequencies.

    Uses a two-step approach:
    1. Check local cache first
    2. If not cached, push a small server-side script, execute via SSH,
       and download the compact frequency JSON (avoids SFTP transfer of 81k samples).

    Returns (sample_counter, token_counter, total_train_samples)
    """
    import paramiko

    # Try local cache first
    cache_file = cache_path or (OUTPUT_DIR / "training_frequencies.json")
    if cache_file.exists():
        print(f"  Using cached frequencies: {cache_file}")
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sample_counter = Counter(data.get('sample_freq', {}))
        token_counter = Counter(data.get('token_freq', {}))
        total_train = data.get('total_train', 0)
        print(f"  Cached: {total_train} train samples, {len(sample_counter)} unique L3 codes")
        return sample_counter, token_counter, total_train

    print(f"  Computing frequencies server-side (avoids large SFTP)...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=30)

    # Push a small server-side script
    compute_script = '''import json
from collections import Counter
wf = json.load(open('/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/labeled_workflows_l3_v4_quality_gate_qgis_vector_oversampled.json'))
splits = json.load(open('/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/dataset_splits_v4_quality_gate_qgis_vector_oversampled.json'))
train_idx = set(splits['train_indices'])
samples = wf['labeled_workflows']
sc = Counter()
tc = Counter()
for i in train_idx:
    codes = [c for c in (samples[i].get('l3_codes', []) + samples[i].get('l3_sequence', [])) if isinstance(c, str) and c.startswith('L3_')]
    sc.update(set(codes))
    tc.update(codes)
print(json.dumps({'total_train': len(train_idx), 'total_samples': len(samples), 'sample_freq': dict(sc), 'token_freq': dict(tc)}))
'''
    sftp = ssh.open_sftp()
    with sftp.open('/home/qy/system_redesign/_compute_freqs.py', 'w') as f:
        f.write(compute_script)
    sftp.close()

    sin, sout, serr = ssh.exec_command(
        'cd /home/qy/system_redesign && python3 _compute_freqs.py', timeout=60
    )
    result = sout.read().decode().strip()
    err = serr.read().decode().strip()
    ssh.close()

    if err:
        print(f"  [WARN] Server stderr: {err[:300]}")
    if not result:
        print(f"  [ERROR] Empty result from server")
        return Counter(), Counter(), 0

    data = json.loads(result)
    total_train = data.get('total_train', 0)

    # Cache locally for next time
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    print(f"  Cached to {cache_file}")

    sample_counter = Counter(data.get('sample_freq', {}))
    token_counter = Counter(data.get('token_freq', {}))
    print(f"  {total_train} train samples, {len(sample_counter)} unique L3 codes")
    return sample_counter, token_counter, total_train


def compute_coverage(
    hierarchy: Dict[str, dict],
    mapped_scores: dict,
    discovered_mappings: dict,
    sample_freq: Counter,
    token_freq: Counter,
    total_train: int,
) -> List[L3CoverageInfo]:
    """Compute coverage info for all L3 codes in the hierarchy."""

    results = []
    for code, info in hierarchy.items():
        cov = L3CoverageInfo(
            l3_code=code,
            l3_name=info['l3_name'],
            l3_description=info['l3_description'],
            l2_code=info['l2_code'],
            l2_name=info['l2_name'],
            l1_code=info['l1_code'],
            l1_name=info['l1_name'],
            freq_v2=info['freq_v2'],
            training_sample_count=sample_freq.get(code, 0),
            training_token_freq=token_freq.get(code, 0),
            total_train_samples=total_train,
            is_vector=code.startswith('L3_02'),
        )

        # QGIS mapped coverage
        if code in mapped_scores:
            mapped_entries = mapped_scores[code]
            cov.qgis_mapped_count = len(mapped_entries)
            cov.max_semantic_score = max(
                (e.get('semantic_score', 0) for e in mapped_entries), default=0.0
            )
            cov.top_qgis_operators = mapped_entries[:5]  # top 5

        # QGIS discovered coverage
        if code in discovered_mappings:
            disc_entries = discovered_mappings[code]
            cov.qgis_discovered_count = len(disc_entries)
            if cov.max_semantic_score == 0.0:
                cov.max_semantic_score = max(
                    (e.get('semantic_score', 0) for e in disc_entries), default=0.0
                )
            # Merge discovered into top operators
            existing_names = {e['qgis_name'] for e in cov.top_qgis_operators}
            for e in disc_entries[:3]:
                if e['qgis_name'] not in existing_names:
                    cov.top_qgis_operators.append(e)

        # Classify gap type
        has_training = cov.training_sample_count > CRITICAL_TRAINING_SAMPLES
        has_low_training = cov.training_sample_count < MIN_TRAINING_SAMPLES
        has_any_qgis = cov.total_qgis_ops > 0   # mapped OR discovered
        has_strong_qgis = cov.qgis_mapped_count >= MIN_QGIS_OPERATORS

        if not has_training and has_any_qgis:
            cov.gap_type = "DATA_GAP"
        elif not has_training and not has_any_qgis:
            cov.gap_type = "BOTH_GAP"
        elif has_any_qgis and has_low_training:
            cov.gap_type = "LOW_COVERAGE"
        elif not has_any_qgis and has_low_training:
            cov.gap_type = "LOW_COVERAGE_NO_QGIS"
        elif not has_any_qgis:
            cov.gap_type = "MAPPING_GAP"
        else:
            cov.gap_type = "ADEQUATE"

        # Compute risk score (0-1, higher = more at risk)
        # Components:
        #   training_risk:  1.0 if 0 samples, decays to 0 at MIN_TRAINING_SAMPLES
        #   qgis_risk:      1.0 if no QGIS operators, decays to 0 at MIN_QGIS_OPERATORS
        #   semantic_risk:  1.0 if no semantic match, decays to 0 at MIN_SEMANTIC_SCORE
        training_risk = max(0.0, 1.0 - cov.training_sample_count / max(MIN_TRAINING_SAMPLES, 1))
        qgis_risk = max(0.0, 1.0 - cov.total_qgis_ops / max(MIN_QGIS_OPERATORS, 1))
        semantic_risk = max(0.0, 1.0 - cov.max_semantic_score / MIN_SEMANTIC_SCORE)

        # Weight: training is most important (0.5), qgis mapping (0.3), semantic (0.2)
        cov.risk_score = round(
            0.50 * training_risk + 0.30 * qgis_risk + 0.20 * semantic_risk, 4
        )

        results.append(cov)

    return results


def render_markdown_report(results: List[L3CoverageInfo]) -> str:
    """Render a human-readable markdown gap report."""

    # Sort by risk score descending
    sorted_results = sorted(results, key=lambda r: r.risk_score, reverse=True)

    # Summary stats
    gap_counts = Counter(r.gap_type for r in results)
    total = len(results)
    vector_total = sum(1 for r in results if r.is_vector)
    critical = sum(1 for r in results if r.training_sample_count == 0)
    critical_vector = sum(
        1 for r in results if r.training_sample_count == 0 and r.is_vector
    )

    lines = []
    lines.append("# L3 Code Coverage Gap Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total L3 codes in vocab | {total} |")
    lines.append(f"| Vector codes (L3_02) | {vector_total} |")
    lines.append(f"| Codes with ZERO training samples | **{critical}** |")
    lines.append(f"| Vector codes with ZERO training | **{critical_vector}** |")
    lines.append(f"| DATA_GAP (has QGIS, no training) | {gap_counts.get('DATA_GAP', 0)} |")
    lines.append(f"| MAPPING_GAP (no QGIS mapped) | {gap_counts.get('MAPPING_GAP', 0)} |")
    lines.append(f"| BOTH_GAP (no data, no QGIS) | {gap_counts.get('BOTH_GAP', 0)} |")
    lines.append(f"| LOW_COVERAGE | {gap_counts.get('LOW_COVERAGE', 0)} |")
    lines.append(f"| LOW_COVERAGE_NO_QGIS | {gap_counts.get('LOW_COVERAGE_NO_QGIS', 0)} |")
    lines.append(f"| ADEQUATE | {gap_counts.get('ADEQUATE', 0)} |")
    lines.append("")

    # Gap type legend
    lines.append("### Gap Type Legend")
    lines.append("")
    lines.append("| Gap Type | Meaning | Action |")
    lines.append("|----------|---------|--------|")
    lines.append("| **DATA_GAP** | QGIS operators exist but ZERO training samples | **Priority 1**: Mine QGIS scripts for this code |")
    lines.append("| **BOTH_GAP** | No training data AND no QGIS mapping | **Priority 2**: Expand crosswalk first, then mine |")
    lines.append("| **MAPPING_GAP** | Has training but no QGIS operators mapped | **Priority 3**: Add crosswalk entries |")
    lines.append("| **LOW_COVERAGE** | Has some training but below threshold | **Priority 4**: Upsample or augment |")
    lines.append("| **LOW_COVERAGE_NO_QGIS** | Low training + no QGIS mapping | **Priority 5**: Both crosswalk + data needed |")
    lines.append("")

    # ── Critical: DATA_GAP codes ──
    lines.append("## Priority 1: DATA_GAP (QGIS operators exist, ZERO training)")
    lines.append("")
    data_gaps = [r for r in sorted_results if r.gap_type == "DATA_GAP"]
    if data_gaps:
        lines.append("These codes have semantically-mapped QGIS operators but **zero training samples**.")
        lines.append("They are the lowest-hanging fruit: mine QGIS scripts using the listed operators.")
        lines.append("")
        lines.append("| L3 Code | Name | L1 | L2 | QGIS Ops | Top Semantic | Top QGIS Operators |")
        lines.append("|---------|------|----|----|---------|-------------|-------------------|")
        for r in data_gaps:
            top_ops = ", ".join(
                f"`{e['qgis_name']}`" for e in r.top_qgis_operators[:3]
            )
            lines.append(
                f"| `{r.l3_code}` | {r.l3_name} | {r.l1_name} | {r.l2_name} | "
                f"{r.qgis_mapped_count} | {r.max_semantic_score:.3f} | {top_ops} |"
            )
        lines.append("")
    else:
        lines.append("✅ No DATA_GAP codes found.")
        lines.append("")

    # ── BOTH_GAP codes ──
    lines.append("## Priority 2: BOTH_GAP (No QGIS mapping AND no training)")
    lines.append("")
    both_gaps = [r for r in sorted_results if r.gap_type == "BOTH_GAP"]
    if both_gaps:
        lines.append("These codes have neither QGIS operator mappings nor training samples.")
        lines.append("Need crosswalk expansion + targeted data generation.")
        lines.append("")
        lines.append("| L3 Code | Name | L1 | L2 | Max Semantic | Discovered QGIS |")
        lines.append("|---------|------|----|----|-------------|-----------------|")
        for r in both_gaps:
            discovered = ", ".join(
                f"`{e['qgis_name']}` ({e.get('semantic_score', 0):.2f})"
                for e in r.top_qgis_operators[:3]
            ) if r.top_qgis_operators else "—"
            lines.append(
                f"| `{r.l3_code}` | {r.l3_name} | {r.l1_name} | {r.l2_name} | "
                f"{r.max_semantic_score:.3f} | {discovered} |"
            )
        lines.append("")
    else:
        lines.append("✅ No BOTH_GAP codes found.")
        lines.append("")

    # ── LOW_COVERAGE codes ──
    lines.append("## Priority 3-4: LOW_COVERAGE (below threshold)")
    lines.append("")
    low_cov = [r for r in sorted_results if r.gap_type.startswith("LOW_COVERAGE")]
    if low_cov:
        lines.append("| L3 Code | Name | L1 | Train Samples | Train % | QGIS Ops | Risk | Gap Type |")
        lines.append("|---------|------|----|-------------|--------|---------|------|----------|")
        for r in low_cov:
            lines.append(
                f"| `{r.l3_code}` | {r.l3_name} | {r.l1_name} | "
                f"{r.training_sample_count} | {r.training_pct:.2f}% | "
                f"{r.qgis_mapped_count} | {r.risk_score:.3f} | {r.gap_type} |"
            )
        lines.append("")

    # ── Complete ranked table (all codes) ──
    lines.append("## Full Coverage Matrix (ranked by risk)")
    lines.append("")
    lines.append("| # | L3 Code | Name | L1 | Train N | Train % | Token Freq | QGIS Ops | Max Sem | Risk | Gap Type |")
    lines.append("|---|---------|------|----|---------|--------|-----------|---------|--------|------|----------|")
    for i, r in enumerate(sorted_results, 1):
        risk_flag = "🔴" if r.risk_score > 0.7 else ("🟡" if r.risk_score > 0.3 else "🟢")
        lines.append(
            f"| {i} | `{r.l3_code}` | {r.l3_name} | {r.l1_name} | "
            f"{r.training_sample_count} | {r.training_pct:.2f}% | "
            f"{r.training_token_freq} | {r.qgis_mapped_count} | "
            f"{r.max_semantic_score:.3f} | {risk_flag} {r.risk_score:.3f} | {r.gap_type} |"
        )
    lines.append("")

    # ── Vector-specific section ──
    lines.append("## Vector Codes (L3_02) Deep Dive")
    lines.append("")
    vector_results = sorted(
        [r for r in results if r.is_vector], key=lambda r: r.risk_score, reverse=True
    )
    lines.append("| L3 Code | Name | Train N | Token Freq | QGIS Ops | Max Sem | Risk | Gap Type | Top QGIS |")
    lines.append("|---------|------|---------|-----------|---------|--------|------|----------|----------|")
    for r in vector_results:
        top_ops = ", ".join(
            f"`{e['qgis_name']}`" for e in r.top_qgis_operators[:2]
        ) if r.top_qgis_operators else "—"
        lines.append(
            f"| `{r.l3_code}` | {r.l3_name} | {r.training_sample_count} | "
            f"{r.training_token_freq} | {r.qgis_mapped_count} | "
            f"{r.max_semantic_score:.3f} | {r.risk_score:.3f} | {r.gap_type} | {top_ops} |"
        )
    lines.append("")

    # ── Recommendations ──
    lines.append("## Recommended Actions")
    lines.append("")

    # DATA_GAP recommendations
    if data_gaps:
        lines.append("### 1. Targeted Script Mining (DATA_GAP codes)")
        lines.append("")
        lines.append("For each DATA_GAP code, search the 68k QGIS script pool for the listed")
        lines.append("QGIS operators and feed matching scripts through the LLM→L3 pipeline.")
        lines.append("")
        for r in data_gaps:
            ops = [e['qgis_name'] for e in r.top_qgis_operators[:5]]
            lines.append(f"- **`{r.l3_code}` ({r.l3_name})**: search for `{'`, `'.join(ops)}`")
        lines.append("")

    # Both gap
    if both_gaps:
        lines.append("### 2. Crosswalk Expansion + Mining (BOTH_GAP codes)")
        lines.append("")
        for r in both_gaps:
            if r.top_qgis_operators:
                best = r.top_qgis_operators[0]
                lines.append(
                    f"- **`{r.l3_code}` ({r.l3_name})**: best discovered QGIS = "
                    f"`{best['qgis_name']}` (sem={best.get('semantic_score', 0):.3f}) — "
                    f"consider adding to crosswalk"
                )
            else:
                lines.append(
                    f"- **`{r.l3_code}` ({r.l3_name})**: no QGIS candidates — "
                    f"may need new QGIS operator discovery"
                )
        lines.append("")

    # Low coverage
    if low_cov:
        lines.append("### 3. Upsampling / Augmentation (LOW_COVERAGE codes)")
        lines.append("")
        lines.append("These codes have some training data but below the recommended minimum")
        lines.append(f"of {MIN_TRAINING_SAMPLES} samples. Enable family-sampler with higher weight")
        lines.append("on these codes, or use API-trace clean data to supplement.")
        lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("L3 Coverage Gap Analyzer")
    print("=" * 60)

    # 1. Load hierarchy
    print("\n[1/4] Loading classification hierarchy...")
    hierarchy = load_hierarchy(HIERARCHY_PATH)
    print(f"  Loaded {len(hierarchy)} L3 codes from hierarchy")

    # Count by L1
    l1_counts = Counter(info['l1_name'] for info in hierarchy.values())
    for l1, cnt in l1_counts.most_common():
        print(f"    {l1}: {cnt}")

    # 2. Load semantic scores
    print("\n[2/4] Loading semantic scores...")
    mapped_scores, discovered_mappings = load_semantic_scores(SEMANTIC_SCORES_PATH)
    print(f"  Mapped (crosswalk): {len(mapped_scores)} L3 codes")
    print(f"  Discovered only: {len(discovered_mappings)} L3 codes")

    # Check how many hierarchy codes have semantic data
    hierarchy_mapped = sum(1 for c in hierarchy if c in mapped_scores)
    hierarchy_discovered = sum(1 for c in hierarchy if c in discovered_mappings)
    hierarchy_both = sum(1 for c in hierarchy if c in mapped_scores or c in discovered_mappings)
    hierarchy_none = sum(1 for c in hierarchy if c not in mapped_scores and c not in discovered_mappings)
    print(f"  Hierarchy codes with mapped QGIS: {hierarchy_mapped}")
    print(f"  Hierarchy codes with discovered QGIS: {hierarchy_discovered}")
    print(f"  Hierarchy codes with any QGIS: {hierarchy_both}")
    print(f"  Hierarchy codes with NO QGIS: {hierarchy_none}")

    # 3. Fetch training data frequencies
    print("\n[3/4] Fetching training data frequencies from server...")
    try:
        sample_freq, token_freq, total_train = fetch_training_frequencies()
    except Exception as e:
        print(f"  [ERROR] Cannot fetch training data: {e}")
        print("  [FALLBACK] Using empty frequencies — will report all codes as gaps")
        sample_freq = Counter()
        token_freq = Counter()
        total_train = 0

    # 4. Compute coverage
    print("\n[4/4] Computing coverage matrix...")
    results = compute_coverage(
        hierarchy, mapped_scores, discovered_mappings,
        sample_freq, token_freq, total_train
    )

    # Sort by risk
    results.sort(key=lambda r: r.risk_score, reverse=True)

    # Print top findings
    print(f"\n{'='*60}")
    print("TOP FINDINGS")
    print(f"{'='*60}")

    gap_counts = Counter(r.gap_type for r in results)
    critical = sum(1 for r in results if r.training_sample_count == 0)
    print(f"\n  Critical (zero training): {critical}/{len(results)} L3 codes")
    print(f"  DATA_GAP:   {gap_counts.get('DATA_GAP', 0)}")
    print(f"  BOTH_GAP:   {gap_counts.get('BOTH_GAP', 0)}")
    print(f"  MAPPING_GAP:{gap_counts.get('MAPPING_GAP', 0)}")
    print(f"  LOW_COV:    {gap_counts.get('LOW_COVERAGE', 0)}")
    print(f"  ADEQUATE:   {gap_counts.get('ADEQUATE', 0)}")

    print(f"\n  Top-10 highest risk L3 codes:")
    print(f"  {'Code':<16} {'Name':<24} {'Train':>6} {'QGIS':>5} {'Sem':>6} {'Risk':>6} {'Type'}")
    print(f"  {'-'*16} {'-'*24} {'-'*6} {'-'*5} {'-'*6} {'-'*6} {'-'*15}")
    for r in results[:10]:
        print(
            f"  {r.l3_code:<16} {r.l3_name:<24} {r.training_sample_count:>6} "
            f"{r.qgis_mapped_count:>5} {r.max_semantic_score:>6.3f} {r.risk_score:>6.3f} {r.gap_type}"
        )

    # Vector-only top risks
    vector_risks = [r for r in results if r.is_vector]
    print(f"\n  Vector (L3_02) codes ranked by risk:")
    print(f"  {'Code':<16} {'Name':<24} {'Train':>6} {'QGIS':>5} {'Sem':>6} {'Risk':>6} {'Type'}")
    print(f"  {'-'*16} {'-'*24} {'-'*6} {'-'*5} {'-'*6} {'-'*6} {'-'*15}")
    for r in vector_risks:
        print(
            f"  {r.l3_code:<16} {r.l3_name:<24} {r.training_sample_count:>6} "
            f"{r.qgis_mapped_count:>5} {r.max_semantic_score:>6.3f} {r.risk_score:>6.3f} {r.gap_type}"
        )

    # ── Output ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = OUTPUT_DIR / "l3_coverage_gap_report.json"
    json_output = {
        "generated_by": "analyze_l3_coverage_gaps.py",
        "thresholds": {
            "min_training_samples": MIN_TRAINING_SAMPLES,
            "critical_training_samples": CRITICAL_TRAINING_SAMPLES,
            "min_qgis_operators": MIN_QGIS_OPERATORS,
            "min_semantic_score": MIN_SEMANTIC_SCORE,
        },
        "summary": {
            "total_l3_codes": len(results),
            "critical_zero_training": critical,
            "gap_counts": dict(gap_counts),
        },
        "results": [
            {
                "l3_code": r.l3_code,
                "l3_name": r.l3_name,
                "l3_description": r.l3_description,
                "l2_code": r.l2_code,
                "l2_name": r.l2_name,
                "l1_code": r.l1_code,
                "l1_name": r.l1_name,
                "is_vector": r.is_vector,
                "training_sample_count": r.training_sample_count,
                "training_token_freq": r.training_token_freq,
                "training_pct": round(r.training_pct, 4),
                "qgis_mapped_count": r.qgis_mapped_count,
                "qgis_discovered_count": r.qgis_discovered_count,
                "max_semantic_score": r.max_semantic_score,
                "top_qgis_operators": r.top_qgis_operators[:5],
                "gap_type": r.gap_type,
                "risk_score": r.risk_score,
            }
            for r in results
        ],
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    print(f"\n  [OK] JSON report → {json_path}")

    # Markdown
    md_path = OUTPUT_DIR / "l3_coverage_gap_report.md"
    md_content = render_markdown_report(results)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"  [OK] Markdown report → {md_path}")

    print(f"\n[DONE] Gap analysis complete.")
    print(f"  Review the Markdown report for prioritized action items.")


if __name__ == "__main__":
    main()
