"""
05_multi_session.py
Multi-session validation: does VISp > VISam replicate across sessions?

Phase 4 of the neuro-omission-decoding project. Orchestrates:
  1. Session selection — picks N sessions maximizing genotype/mouse diversity
  2. Spike extraction — 400–750ms clean window (D012) + 0–750ms time-resolved
  3. Decoding — late-window + time-resolved per session
  4. Aggregation — paired Wilcoxon test, effect sizes, summary figures

Imports core functions from 02_extract_spikes.py and 04_decode.py rather than
calling them as subprocesses — avoids redundant cache initialization.

Usage:
    # Quick validation (5 sessions, 100 permutations)
    python 05_multi_session.py --n_sessions 5 --n_permutations 100

    # Full run (5 sessions, 1000 permutations)
    python 05_multi_session.py --n_sessions 5 --n_permutations 1000

    # Resume: add sessions to reach n=10 total (loads previous results, runs only new)
    python 05_multi_session.py --n_sessions 10 --n_permutations 100 --resume

    # Specific sessions (skip auto-selection)
    python 05_multi_session.py --session_ids 1064644573 1064646791 1064655940

    # Dry run: just show which sessions would be selected
    python 05_multi_session.py --n_sessions 10 --dry_run
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

# ── Imports from project scripts ────────────────────────────────────────────
# Add parent directory to path so we can import sibling scripts
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allensdk.brain_observatory.behavior.behavior_project_cache.behavior_neuropixels_project_cache import (
    VisualBehaviorNeuropixelsProjectCache,
)

# We import the core functions directly from existing scripts.
# This avoids code duplication and ensures consistency.
from importlib.util import spec_from_file_location, module_from_spec


def _import_module(name, path):
    """Import a module from a file path (handles numeric-prefixed filenames)."""
    spec = spec_from_file_location(name, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


extract_mod = _import_module("extract_spikes", SCRIPT_DIR / "02_extract_spikes.py")
decode_mod = _import_module("decode", SCRIPT_DIR / "04_decode.py")

# Re-export the functions we need
get_quality_unit_ids = extract_mod.get_quality_unit_ids
process_session = extract_mod.process_session
get_viable_session_ids = extract_mod.get_viable_session_ids

load_session_data = decode_mod.load_session_data
decode_with_undersampling = decode_mod.decode_with_undersampling
permutation_test = decode_mod.permutation_test
compute_p_value = decode_mod.compute_p_value

# ── Config ──────────────────────────────────────────────────────────────────

AREAS = ["VISp", "VISam"]
MIN_UNITS_PER_AREA = 20
QUALITY_FILTERS = extract_mod.QUALITY_FILTERS

# Primary analysis window (D012: past both ON and OFF transients)
LATE_WINDOW_MS = (400, 750)
LATE_BIN_MS = 350
LATE_TAG = "w400-750ms_b350ms"

# Time-resolved: 0–500ms matches existing R006/R008 extraction and narrative
# (shows ON-response peak, OFF-response confound, decay into late window)
# Extend to 0–750ms later (R011) once this pipeline is validated
TR_WINDOW_MS = (0, 500)
TR_BIN_MS = 50
TR_TAG = "w0-500ms_b50ms"

# Decoding params
N_FOLDS = 5
N_UNDERSAMPLE_REPEATS = 10
RANDOM_SEED = 42


# ── Resume support ──────────────────────────────────────────────────────────


def load_previous_results(output_dir):
    """Load previous multi_session_results.json if it exists.

    Returns:
        previous_session_results: list of per-session result dicts, or []
        previous_session_ids: set of session IDs already completed
    """
    results_path = Path(output_dir) / "multi_session_results.json"
    if not results_path.exists():
        return [], set()

    with open(results_path) as f:
        data = json.load(f)

    session_results = data.get("session_results", [])
    completed = [
        r for r in session_results
        if r.get("status") == "complete"
    ]
    completed_ids = {r["session_id"] for r in completed}

    print(f"\nLoaded {len(completed)} previous results from {results_path}")
    for r in completed:
        geno = r.get("genotype_short", "?")
        mouse = r.get("mouse_id", "?")
        acc_v = r.get("VISp_accuracy", "?")
        acc_a = r.get("VISam_accuracy", "?")
        print(f"  {r['session_id']}  genotype={geno}  mouse={mouse}  "
              f"VISp={acc_v}  VISam={acc_a}")

    return completed, completed_ids


def backup_previous_results(output_dir):
    """Create a timestamped backup of existing results before overwriting."""
    results_path = Path(output_dir) / "multi_session_results.json"
    if results_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = results_path.with_name(f"multi_session_results_backup_{ts}.json")
        import shutil
        shutil.copy2(results_path, backup_path)
        print(f"Backed up previous results to {backup_path.name}")


# ── Session selection ───────────────────────────────────────────────────────


def select_sessions(cache, units_table, n_sessions=5, exclude_ids=None,
                    seen_genotypes_seed=None, seen_mice_seed=None):
    """Select sessions maximizing genotype and mouse diversity.

    Strategy:
      1. Get all viable sessions (both VISp + VISam recorded)
      2. Filter to those meeting unit count thresholds
      3. Sort by genotype diversity, then by mouse_id diversity
      4. Greedily pick sessions: prefer unseen genotype, then unseen mouse

    Args:
        cache: VBN project cache
        units_table: pre-loaded unit table
        n_sessions: number of NEW sessions to select
        exclude_ids: session IDs to skip (e.g., already processed)
        seen_genotypes_seed: set of genotypes already in the dataset (for diversity)
        seen_mice_seed: set of mouse_ids already in the dataset (for diversity)

    Returns:
        selected: list of dicts with session_id, genotype, mouse_id, unit counts
    """
    if exclude_ids is None:
        exclude_ids = set()
    else:
        exclude_ids = set(exclude_ids)

    sessions = cache.get_ecephys_session_table()
    viable_ids = get_viable_session_ids(cache)

    # Build candidate table with metadata
    candidates = []
    for sid in viable_ids:
        if sid in exclude_ids:
            continue

        row = sessions.loc[sid]

        # Get unit counts per area
        unit_counts = {}
        viable = True
        for area in AREAS:
            uids = get_quality_unit_ids(units_table, sid, area)
            unit_counts[area] = len(uids)
            if len(uids) < MIN_UNITS_PER_AREA:
                viable = False
                break

        if not viable:
            continue

        # Extract genotype and mouse_id
        genotype = str(row.get("genotype", "unknown"))
        mouse_id = int(row.get("mouse_id", -1)) if "mouse_id" in row.index else -1

        # Some sessions have full_genotype; normalize to short form.
        # In the Allen VBN dataset:
        #   SST-IRES-Cre lines → "Sst-IRES-Cre/wt;Ai32..."
        #   VIP-IRES-Cre lines → "Vip-IRES-Cre/wt;Ai32..."
        #   Slc17a7-IRES2-Cre  → often appears as "wt/wt" in the genotype
        #     field because the Cre allele is on a different locus.
        # All three lines record from the full extracellular population;
        # the Cre line only determines which cell type is opto-taggable.
        if "Sst" in genotype or "SST" in genotype:
            geno_short = "SST"
        elif "Vip" in genotype or "VIP" in genotype:
            geno_short = "VIP"
        elif "Slc17a7" in genotype:
            geno_short = "Slc17a7"
        elif genotype == "wt/wt":
            geno_short = "Slc17a7"  # excitatory Cre line in Allen VBN
        else:
            geno_short = genotype[:20]

        candidates.append({
            "session_id": sid,
            "genotype": genotype,
            "genotype_short": geno_short,
            "mouse_id": mouse_id,
            "n_units_VISp": unit_counts["VISp"],
            "n_units_VISam": unit_counts["VISam"],
            "total_units": sum(unit_counts.values()),
        })

    if not candidates:
        raise ValueError("No viable candidate sessions found.")

    df = pd.DataFrame(candidates)
    print(f"\nCandidate sessions: {len(df)}")
    print(f"Genotypes: {df['genotype_short'].value_counts().to_dict()}")
    print(f"Unique mice: {df['mouse_id'].nunique()}")

    # Greedy selection: maximize genotype diversity, then mouse diversity
    selected = []
    seen_genotypes = set(seen_genotypes_seed) if seen_genotypes_seed else set()
    seen_mice = set(seen_mice_seed) if seen_mice_seed else set()

    # Pass 1: one session per genotype (highest unit count as tiebreaker)
    for geno in df["genotype_short"].unique():
        if len(selected) >= n_sessions:
            break
        geno_df = df[df["genotype_short"] == geno].sort_values(
            "total_units", ascending=False
        )
        for _, row in geno_df.iterrows():
            if row["mouse_id"] not in seen_mice or len(seen_genotypes) < 3:
                selected.append(row.to_dict())
                seen_genotypes.add(geno)
                seen_mice.add(row["mouse_id"])
                break

    # Pass 2: fill remaining slots with unseen mice, highest unit count
    if len(selected) < n_sessions:
        remaining = df[~df["session_id"].isin([s["session_id"] for s in selected])]
        # Prefer unseen mice
        unseen_mice = remaining[~remaining["mouse_id"].isin(seen_mice)]
        if not unseen_mice.empty:
            unseen_mice = unseen_mice.sort_values("total_units", ascending=False)
            for _, row in unseen_mice.iterrows():
                if len(selected) >= n_sessions:
                    break
                selected.append(row.to_dict())
                seen_mice.add(row["mouse_id"])

    # Pass 3: if still need more, take best remaining
    if len(selected) < n_sessions:
        remaining = df[~df["session_id"].isin([s["session_id"] for s in selected])]
        remaining = remaining.sort_values("total_units", ascending=False)
        for _, row in remaining.iterrows():
            if len(selected) >= n_sessions:
                break
            selected.append(row.to_dict())

    return selected[:n_sessions]


# ── Per-session pipeline ────────────────────────────────────────────────────


def run_session_pipeline(cache, session_id, units_table, spike_dir, decode_dir,
                         n_permutations=100, skip_extraction=False):
    """Run extraction + decoding for one session.

    Returns:
        result: dict with per-area accuracies, p-values, and metadata
    """
    result = {"session_id": int(session_id), "status": "started"}
    t0 = time.time()

    # ── Extraction ──
    late_data_path = Path(spike_dir) / f"session_{session_id}" / LATE_TAG
    tr_data_path = Path(spike_dir) / f"session_{session_id}" / TR_TAG

    if not skip_extraction or not late_data_path.exists():
        print(f"\n  Extracting 400–750ms window...")
        try:
            meta = process_session(
                cache, session_id,
                window_ms=LATE_WINDOW_MS,
                bin_width_ms=LATE_BIN_MS,
                output_dir=spike_dir,
                units_table=units_table,
            )
            if meta is None:
                result["status"] = "skipped_low_units"
                return result
        except Exception as e:
            result["status"] = f"extraction_error: {e}"
            return result
    else:
        print(f"  Late-window data exists, skipping extraction.")

    if not skip_extraction or not tr_data_path.exists():
        print(f"\n  Extracting 0–750ms time-resolved...")
        try:
            process_session(
                cache, session_id,
                window_ms=TR_WINDOW_MS,
                bin_width_ms=TR_BIN_MS,
                output_dir=spike_dir,
                units_table=units_table,
            )
        except Exception as e:
            print(f"  WARNING: Time-resolved extraction failed: {e}")
            # Non-fatal — we can still do late-window analysis

    # ── Late-window decoding ──
    print(f"\n  Decoding (late window, {n_permutations} permutations)...")
    late_results = {}

    for area in AREAS:
        try:
            rates, labels, metadata = load_session_data(
                spike_dir, session_id, LATE_TAG, area
            )
        except FileNotFoundError as e:
            result["status"] = f"missing_data: {e}"
            return result

        n_omit = int(np.sum(labels == 1))
        n_units = rates.shape[1]

        print(f"    {area}: {n_units} units, {n_omit} omissions")

        observed_acc, repeat_means = decode_with_undersampling(
            rates, labels,
            n_repeats=N_UNDERSAMPLE_REPEATS,
            n_folds=N_FOLDS,
            seed=RANDOM_SEED,
        )
        acc_std = float(np.std(repeat_means))

        null_dist = permutation_test(
            rates, labels,
            n_permutations=n_permutations,
            n_folds=N_FOLDS,
            seed=RANDOM_SEED,
        )
        p_value = compute_p_value(observed_acc, null_dist)

        sig = "***" if p_value < 0.01 else ("*" if p_value < 0.05 else "n.s.")
        print(f"    {area}: {observed_acc:.3f} ±{acc_std:.3f} (p={p_value:.4f}) {sig}")

        late_results[area] = {
            "observed_accuracy": float(observed_acc),
            "accuracy_std": acc_std,
            "repeat_means": [float(x) for x in repeat_means],
            "p_value": float(p_value),
            "null_mean": float(null_dist.mean()),
            "null_std": float(null_dist.std()),
            "null_99th": float(np.percentile(null_dist, 99)),
            "null_distribution": [float(x) for x in null_dist],
            "n_units": n_units,
            "n_omission_trials": n_omit,
        }

    # ── Time-resolved decoding (no permutation test) ──
    tr_results = {}
    if tr_data_path.exists():
        print(f"\n  Decoding (time-resolved, no permutations)...")
        for area in AREAS:
            try:
                rates, labels, metadata = load_session_data(
                    spike_dir, session_id, TR_TAG, area
                )
            except FileNotFoundError:
                continue

            n_bins = rates.shape[2]
            bin_edges = metadata["bin_edges_s"]
            bin_centers_ms = [
                (bin_edges[i] + bin_edges[i + 1]) / 2 * 1000
                for i in range(n_bins)
            ]

            bin_accs = []
            for b in range(n_bins):
                rates_bin = rates[:, :, b:b + 1]
                acc, _ = decode_with_undersampling(
                    rates_bin, labels,
                    n_repeats=N_UNDERSAMPLE_REPEATS,
                    n_folds=N_FOLDS,
                    seed=RANDOM_SEED,
                )
                bin_accs.append({
                    "bin_center_ms": float(bin_centers_ms[b]),
                    "accuracy": float(acc),
                })

            tr_results[area] = bin_accs
            peak = max(bin_accs, key=lambda x: x["accuracy"])
            print(f"    {area}: peak {peak['accuracy']:.3f} at {peak['bin_center_ms']:.0f}ms")

    # ── Assemble result ──
    elapsed = time.time() - t0
    result.update({
        "status": "complete",
        "late_window": late_results,
        "time_resolved": tr_results if tr_results else None,
        "elapsed_seconds": round(elapsed, 1),
        "VISp_accuracy": late_results["VISp"]["observed_accuracy"],
        "VISam_accuracy": late_results["VISam"]["observed_accuracy"],
        "diff_VISam_minus_VISp": (
            late_results["VISam"]["observed_accuracy"]
            - late_results["VISp"]["observed_accuracy"]
        ),
    })

    diff = result["diff_VISam_minus_VISp"]
    print(f"\n  VISam − VISp = {diff:+.3f} "
          f"({'VISam better' if diff > 0 else 'VISp better'})")
    print(f"  Session completed in {elapsed:.0f}s")

    return result


# ── Aggregation and statistics ──────────────────────────────────────────────


def aggregate_results(session_results):
    """Compute cross-session statistics from paired VISp/VISam accuracies.

    Returns:
        summary: dict with paired test results, effect sizes, etc.
    """
    from scipy import stats

    completed = [r for r in session_results if r["status"] == "complete"]
    n = len(completed)

    if n < 3:
        print(f"\nWARNING: Only {n} completed sessions. Need ≥3 for paired test.")
        return {"n_sessions": n, "warning": "too_few_sessions"}

    visp_accs = np.array([r["VISp_accuracy"] for r in completed])
    visam_accs = np.array([r["VISam_accuracy"] for r in completed])
    diffs = visam_accs - visp_accs  # positive = VISam better

    # Paired Wilcoxon signed-rank test (non-parametric, appropriate for n=5)
    if n >= 5:
        wilcoxon_stat, wilcoxon_p = stats.wilcoxon(visp_accs, visam_accs,
                                                     alternative="two-sided")
    else:
        # Wilcoxon needs n≥5 for meaningful results; use sign test instead
        n_positive = np.sum(diffs > 0)
        wilcoxon_stat = float(n_positive)
        wilcoxon_p = float(stats.binomtest(n_positive, n, 0.5).pvalue)

    # Effect size: Cohen's d for paired samples
    d_mean = np.mean(diffs)
    d_std = np.std(diffs, ddof=1) if n > 1 else 1.0
    cohens_d = d_mean / d_std if d_std > 0 else 0.0

    # Permutation test on the paired differences (more appropriate for small n)
    rng = np.random.default_rng(RANDOM_SEED)
    n_perm = 10000
    perm_means = np.zeros(n_perm)
    for i in range(n_perm):
        signs = rng.choice([-1, 1], size=n)
        perm_means[i] = np.mean(diffs * signs)
    observed_mean_diff = np.mean(diffs)
    perm_p = (np.sum(np.abs(perm_means) >= np.abs(observed_mean_diff)) + 1) / (n_perm + 1)

    # One-sided sign test: how likely is it that ALL pairs agree by chance?
    n_visp_better = int(np.sum(diffs < 0))
    n_visam_better = int(np.sum(diffs > 0))
    n_concordant = max(n_visp_better, n_visam_better)
    sign_test_p = float(stats.binomtest(n_concordant, n, 0.5,
                                         alternative="greater").pvalue)

    summary = {
        "n_sessions": n,
        "VISp_accuracies": visp_accs.tolist(),
        "VISam_accuracies": visam_accs.tolist(),
        "paired_differences": diffs.tolist(),
        "mean_VISp": float(np.mean(visp_accs)),
        "std_VISp": float(np.std(visp_accs, ddof=1)) if n > 1 else 0.0,
        "mean_VISam": float(np.mean(visam_accs)),
        "std_VISam": float(np.std(visam_accs, ddof=1)) if n > 1 else 0.0,
        "mean_difference": float(observed_mean_diff),
        "std_difference": float(d_std),
        "cohens_d": float(cohens_d),
        "wilcoxon_statistic": float(wilcoxon_stat),
        "wilcoxon_p": float(wilcoxon_p),
        "permutation_p": float(perm_p),
        "sign_test_p": sign_test_p,
        "n_VISp_better": n_visp_better,
        "n_VISam_better": n_visam_better,
        "n_tied": int(np.sum(diffs == 0)),
        "direction": "VISp > VISam" if observed_mean_diff < 0 else "VISam > VISp",
        # Per-session covariate table for reporting
        "session_table": [
            {
                "session_id": r["session_id"],
                "genotype": r.get("genotype_short", "unknown"),
                "mouse_id": r.get("mouse_id", "unknown"),
                "n_units_VISp": r["late_window"]["VISp"]["n_units"],
                "n_units_VISam": r["late_window"]["VISam"]["n_units"],
                "n_omissions": r["late_window"]["VISp"]["n_omission_trials"],
                "VISp_accuracy": r["VISp_accuracy"],
                "VISam_accuracy": r["VISam_accuracy"],
                "diff": r["diff_VISam_minus_VISp"],
                "VISp_p": r["late_window"]["VISp"]["p_value"],
                "VISam_p": r["late_window"]["VISam"]["p_value"],
            }
            for r in completed
        ],
    }

    # Print the session table
    print(f"\n  Per-session results (covariates):")
    print(f"  {'Session':>12s}  {'Geno':>6s}  {'Mouse':>8s}  "
          f"{'VISp_n':>6s}  {'VISam_n':>7s}  {'Omit':>5s}  "
          f"{'VISp':>6s}  {'VISam':>6s}  {'Diff':>7s}")
    print(f"  {'-'*80}")
    for row in summary["session_table"]:
        print(f"  {row['session_id']:>12d}  {row['genotype']:>6s}  {str(row['mouse_id']):>8s}  "
              f"{row['n_units_VISp']:>6d}  {row['n_units_VISam']:>7d}  {row['n_omissions']:>5d}  "
              f"{row['VISp_accuracy']:>6.3f}  {row['VISam_accuracy']:>6.3f}  "
              f"{row['diff']:>+7.3f}")

    return summary


# ── Visualization ───────────────────────────────────────────────────────────


def plot_summary(session_results, summary, output_dir):
    """Generate summary figures for multi-session validation."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skipping plots.")
        return

    completed = [r for r in session_results if r["status"] == "complete"]
    n = len(completed)
    if n < 2:
        return

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    visp_accs = np.array([r["VISp_accuracy"] for r in completed])
    visam_accs = np.array([r["VISam_accuracy"] for r in completed])
    session_ids = [str(r["session_id"])[-6:] for r in completed]

    # ── Panel A: Paired dot plot ──
    ax = axes[0]
    for i in range(n):
        ax.plot([0, 1], [visp_accs[i], visam_accs[i]], "o-",
                color="gray", alpha=0.5, linewidth=1.5, markersize=8)
    ax.plot(0, np.mean(visp_accs), "D", color="#2196F3", markersize=12,
            zorder=5, label=f"VISp mean: {np.mean(visp_accs):.3f}")
    ax.plot(1, np.mean(visam_accs), "D", color="#9C27B0", markersize=12,
            zorder=5, label=f"VISam mean: {np.mean(visam_accs):.3f}")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["VISp", "VISam"], fontsize=12)
    ax.set_ylabel("Decoding accuracy", fontsize=12)
    ax.set_title("Paired comparison (400–750ms)", fontsize=13)
    ax.set_xlim(-0.3, 1.3)
    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.3, label="Chance")
    ax.legend(fontsize=9, loc="lower left")

    # ── Panel B: Difference scores ──
    ax = axes[1]
    diffs = visam_accs - visp_accs
    colors = ["#9C27B0" if d > 0 else "#2196F3" for d in diffs]
    bars = ax.barh(range(n), diffs, color=colors, alpha=0.7, edgecolor="white")
    ax.set_yticks(range(n))
    ax.set_yticklabels(session_ids, fontsize=9)
    ax.axvline(0, color="black", linewidth=1)
    ax.axvline(np.mean(diffs), color="red", linestyle="--", linewidth=1.5,
               label=f"Mean: {np.mean(diffs):+.3f}")
    ax.set_xlabel("VISam − VISp accuracy", fontsize=12)
    ax.set_ylabel("Session", fontsize=12)
    ax.set_title(f"Per-session differences (n={n})", fontsize=13)
    ax.legend(fontsize=9)

    # ── Panel C: Time-resolved (all sessions overlaid) ──
    ax = axes[2]
    area_colors = {"VISp": "#2196F3", "VISam": "#9C27B0"}
    all_curves = {"VISp": [], "VISam": []}

    for r in completed:
        if r.get("time_resolved"):
            for area in AREAS:
                if area in r["time_resolved"]:
                    bins_data = r["time_resolved"][area]
                    centers = [b["bin_center_ms"] for b in bins_data]
                    accs = [b["accuracy"] for b in bins_data]
                    ax.plot(centers, accs, color=area_colors[area],
                            alpha=0.2, linewidth=1)
                    all_curves[area].append(accs)

    # Plot means
    for area in AREAS:
        if all_curves[area]:
            mean_curve = np.mean(all_curves[area], axis=0)
            centers = [b["bin_center_ms"] for b in completed[0]["time_resolved"][area]]
            ax.plot(centers, mean_curve, color=area_colors[area],
                    linewidth=2.5, label=f"{area} (mean)")

    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.3)
    ax.axvline(250, color="gray", linestyle=":", alpha=0.5, label="Stim offset")
    ax.axvspan(400, 750, alpha=0.05, color="green", label="Clean window")
    ax.set_xlabel("Time from stimulus onset (ms)", fontsize=12)
    ax.set_ylabel("Decoding accuracy", fontsize=12)
    ax.set_title("Time-resolved (all sessions)", fontsize=13)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_ylim(0.4, 1.0)

    fig.suptitle(
        f"Multi-Session Validation — Omission Decoding (n={n} sessions)",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout()

    out_path = Path(output_dir) / "multi_session_summary.png"
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"\nSaved summary figure: {out_path}")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Multi-session validation of omission decoding (Phase 4)."
    )
    parser.add_argument(
        "--n_sessions", type=int, default=5,
        help="Number of sessions to select (default: 5).",
    )
    parser.add_argument(
        "--session_ids", type=int, nargs="+", default=None,
        help="Specific session IDs to use (overrides auto-selection).",
    )
    parser.add_argument(
        "--n_permutations", type=int, default=100,
        help="Permutations per session (default: 100; use 1000 for final).",
    )
    parser.add_argument(
        "--cache_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "allen_vbn_cache"),
        help="Allen VBN cache directory.",
    )
    parser.add_argument(
        "--spike_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "spike_matrices"),
        help="Directory for spike extraction outputs.",
    )
    parser.add_argument(
        "--output_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "multi_session"),
        help="Directory for aggregated results.",
    )
    parser.add_argument(
        "--skip_extraction", action="store_true",
        help="Skip extraction if data already exists.",
    )
    parser.add_argument(
        "--exclude_pilot", action="store_true",
        help="Exclude the pilot session (1064644573) from selection.",
    )
    parser.add_argument(
        "--include_pilot", action="store_true",
        help="Include pilot session results in aggregation (if already extracted).",
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Show session selection without processing.",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from previous results: load multi_session_results.json, "
             "skip already-completed sessions, run only new ones to reach "
             "--n_sessions total, then merge and re-aggregate.",
    )
    args = parser.parse_args()

    # ── Initialize ──
    print(f"Cache: {args.cache_dir}")
    cache = VisualBehaviorNeuropixelsProjectCache.from_s3_cache(
        cache_dir=args.cache_dir
    )
    print("Loading unit table...")
    units_table = cache.get_unit_table()

    # ── Session selection ──
    pilot_id = 1064644573

    # ── Resume: load previous results ──
    previous_results = []
    previous_ids = set()
    seen_genotypes_seed = set()
    seen_mice_seed = set()

    if args.resume:
        previous_results, previous_ids = load_previous_results(args.output_dir)
        if previous_results:
            # Seed diversity tracking with already-completed sessions
            for r in previous_results:
                g = r.get("genotype_short")
                m = r.get("mouse_id")
                if g:
                    seen_genotypes_seed.add(g)
                if m:
                    seen_mice_seed.add(m)
            n_needed = max(0, args.n_sessions - len(previous_results))
            print(f"\nResume mode: {len(previous_results)} existing + {n_needed} new "
                  f"= {args.n_sessions} total target")
            if n_needed == 0:
                print("Already at target. Re-aggregating with current results...")
        else:
            n_needed = args.n_sessions
            print("\nNo previous results found. Running full selection.")
    else:
        n_needed = args.n_sessions

    if args.session_ids:
        # Manual override — filter out already-completed if resuming
        manual_ids = [sid for sid in args.session_ids if sid not in previous_ids]
        selected = [{"session_id": sid} for sid in manual_ids]
        print(f"\nUsing {len(selected)} manually specified sessions"
              f" ({len(args.session_ids) - len(manual_ids)} already completed, skipped).")
    elif n_needed > 0:
        exclude = previous_ids.copy()
        if args.exclude_pilot:
            exclude.add(pilot_id)
        selected = select_sessions(
            cache, units_table,
            n_sessions=n_needed,
            exclude_ids=exclude,
            seen_genotypes_seed=seen_genotypes_seed,
            seen_mice_seed=seen_mice_seed,
        )
    else:
        selected = []

    print(f"\n{'='*60}")
    print(f"SELECTED SESSIONS ({len(selected)})")
    print(f"{'='*60}")
    for s in selected:
        geno = s.get("genotype_short", "?")
        mouse = s.get("mouse_id", "?")
        vp = s.get("n_units_VISp", "?")
        va = s.get("n_units_VISam", "?")
        print(f"  {s['session_id']}  genotype={geno}  mouse={mouse}  "
              f"VISp={vp}  VISam={va}")

    if args.dry_run:
        print("\n[DRY RUN] Stopping here.")
        return

    # ── Process new sessions ──
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.spike_dir, exist_ok=True)

    # Back up previous results before overwriting
    if args.resume and previous_results:
        backup_previous_results(args.output_dir)

    new_results = []
    total_t0 = time.time()

    for i, s in enumerate(selected):
        sid = s["session_id"]
        print(f"\n{'='*60}")
        print(f"NEW SESSION {i+1}/{len(selected)}: {sid}")
        print(f"{'='*60}")

        result = run_session_pipeline(
            cache, sid, units_table,
            spike_dir=args.spike_dir,
            decode_dir=args.output_dir,
            n_permutations=args.n_permutations,
            skip_extraction=args.skip_extraction,
        )

        # Add selection metadata
        result.update({k: v for k, v in s.items() if k != "session_id"})
        new_results.append(result)

        # Save intermediate results (new only) after each session
        interim_path = Path(args.output_dir) / "session_results_interim.json"
        with open(interim_path, "w") as f:
            json.dump(new_results, f, indent=2, default=str)

    # ── Merge previous + new results ──
    all_results = list(previous_results) + new_results

    # ── Include pilot if requested ──
    all_session_ids = {r["session_id"] for r in all_results}
    if args.include_pilot and pilot_id not in all_session_ids:
        pilot_late = Path(args.spike_dir) / f"session_{pilot_id}" / LATE_TAG
        if pilot_late.exists():
            print(f"\nIncluding pilot session {pilot_id} in aggregation...")
            # Load pilot results from disk if available, or re-decode
            pilot_result = run_session_pipeline(
                cache, pilot_id, units_table,
                spike_dir=args.spike_dir,
                decode_dir=args.output_dir,
                n_permutations=args.n_permutations,
                skip_extraction=True,
            )
            pilot_result["genotype_short"] = "SST"  # known from ANALYSIS_LOG
            pilot_result["is_pilot"] = True
            all_results.append(pilot_result)

    total_elapsed = time.time() - total_t0

    # ── Aggregate ──
    print(f"\n{'='*60}")
    print(f"AGGREGATION")
    print(f"{'='*60}")

    summary = aggregate_results(all_results)

    print(f"\nCompleted sessions: {summary['n_sessions']}")
    if summary.get("warning"):
        print(f"WARNING: {summary['warning']}")
    else:
        print(f"VISp  mean accuracy: {summary['mean_VISp']:.3f} ± {summary['std_VISp']:.3f}")
        print(f"VISam mean accuracy: {summary['mean_VISam']:.3f} ± {summary['std_VISam']:.3f}")
        print(f"Mean difference (VISam − VISp): {summary['mean_difference']:+.3f}")
        print(f"Direction: {summary['direction']}")
        print(f"Cohen's d: {summary['cohens_d']:.2f}")
        print(f"Wilcoxon p: {summary['wilcoxon_p']:.4f}")
        print(f"Permutation p: {summary['permutation_p']:.4f}")
        print(f"Sign test p: {summary['sign_test_p']:.4f}")
        print(f"VISp better in {summary['n_VISp_better']}/{summary['n_sessions']} sessions")

    # ── Save ──
    output = {
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "late_window_ms": list(LATE_WINDOW_MS),
            "late_bin_ms": LATE_BIN_MS,
            "tr_window_ms": list(TR_WINDOW_MS),
            "tr_bin_ms": TR_BIN_MS,
            "n_permutations": args.n_permutations,
            "n_folds": N_FOLDS,
            "n_undersample_repeats": N_UNDERSAMPLE_REPEATS,
            "quality_filters": QUALITY_FILTERS,
            "min_units_per_area": MIN_UNITS_PER_AREA,
        },
        "summary": summary,
        "session_results": all_results,
        "total_elapsed_seconds": round(total_elapsed, 1),
    }

    final_path = Path(args.output_dir) / "multi_session_results.json"
    with open(final_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nFinal results saved to {final_path}")

    # ── Plot ──
    plot_summary(all_results, summary, args.output_dir)

    # ── Print conclusion ──
    print(f"\n{'='*60}")
    print(f"CONCLUSION (n={summary['n_sessions']} sessions)")
    print(f"{'='*60}")
    if summary.get("warning"):
        print(f"Insufficient data for conclusion ({summary['warning']})")
    else:
        print(f"Direction: {summary['direction']}")
        print(f"Effect size (Cohen's d): {summary['cohens_d']:.2f}")
        print(f"Wilcoxon signed-rank p: {summary['wilcoxon_p']:.4f}")
        print(f"Permutation (sign-flip) p: {summary['permutation_p']:.4f}")
        print(f"One-sided sign test p: {summary['sign_test_p']:.4f}")
        print(f"Concordance: VISp better in {summary['n_VISp_better']}/{summary['n_sessions']}")

        # Highlight which tests pass significance
        sig_tests = []
        if summary["wilcoxon_p"] < 0.05:
            sig_tests.append("Wilcoxon")
        if summary["permutation_p"] < 0.05:
            sig_tests.append("Permutation")
        if summary["sign_test_p"] < 0.05:
            sig_tests.append("Sign test")
        if sig_tests:
            print(f"Significant at p<0.05: {', '.join(sig_tests)}")
        else:
            print(f"No test reaches p<0.05 (but see effect size and concordance)")

    n_prev = len(previous_results) if args.resume else 0
    n_new = len([r for r in new_results if r.get("status") == "complete"]) if selected else 0
    print(f"\nSessions: {n_prev} previous + {n_new} new = {summary['n_sessions']} total")
    print(f"Total runtime: {total_elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()