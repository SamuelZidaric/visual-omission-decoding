"""
07_paired_novelty.py
Within-mouse familiar vs. novel comparison: does the persistent 400–750ms
omission signal depend on learned image expectations?

Design: 2×2 repeated-measures (Area: VISp vs VISam × Experience: Familiar vs Novel)
across 9 mice that each have both a Familiar and a Novel recording session.

Pipeline:
  1. Load familiar baselines from multi_session_results.json (already computed)
  2. Run 400–750ms extraction + decoding on the 9 matched Novel sessions
  3. Compute within-mouse deltas (Familiar → Novel) for each area
  4. Statistical tests on the deltas
  5. Generate paired slope plots

Usage:
    # Full run
    python 07_paired_novelty.py --n_permutations 100

    # Dry run: show paired sessions without processing
    python 07_paired_novelty.py --dry_run

    # Skip extraction if novel spike data already cached
    python 07_paired_novelty.py --n_permutations 100 --skip_extraction
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
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from allensdk.brain_observatory.behavior.behavior_project_cache.behavior_neuropixels_project_cache import (
    VisualBehaviorNeuropixelsProjectCache,
)

from importlib.util import spec_from_file_location, module_from_spec


def _import_module(name, path):
    spec = spec_from_file_location(name, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


extract_mod = _import_module("extract_spikes", SCRIPT_DIR / "02_extract_spikes.py")
decode_mod = _import_module("decode", SCRIPT_DIR / "04_decode.py")

get_quality_unit_ids = extract_mod.get_quality_unit_ids
process_session = extract_mod.process_session
load_session_data = decode_mod.load_session_data
decode_with_undersampling = decode_mod.decode_with_undersampling
permutation_test = decode_mod.permutation_test
compute_p_value = decode_mod.compute_p_value

# ── Config ──────────────────────────────────────────────────────────────────

AREAS = ["VISp", "VISam"]

# Same window as the familiar analysis (D012)
LATE_WINDOW_MS = (400, 750)
LATE_BIN_MS = 350
LATE_TAG = "w400-750ms_b350ms"

# Decoding params — match 05_multi_session.py exactly
N_FOLDS = 5
N_UNDERSAMPLE_REPEATS = 10
RANDOM_SEED = 42

# ── Paired session mapping ──────────────────────────────────────────────────
# mouse_id → (familiar_session_id, novel_session_id)
# 9 mice with both Familiar and Novel sessions passing unit thresholds.
# Mouse 585329 excluded: novel session (1140102579) has only 17 VISam units.

PAIRED_SESSIONS = {
    570299: {"familiar": 1115077618, "novel": 1115356973},
    568963: {"familiar": 1111013640, "novel": 1111216934},
    578003: {"familiar": 1119946360, "novel": 1120251466},
    574078: {"familiar": 1115086689, "novel": 1115368723},
    576323: {"familiar": 1116941914, "novel": 1117148442},
    570301: {"familiar": 1108334384, "novel": 1108531612},
    599294: {"familiar": 1152632711, "novel": 1152811536},
    560962: {"familiar": 1099598937, "novel": 1099869737},
    544836: {"familiar": 1067588044, "novel": 1067781390},
}


# ── Load familiar baselines ─────────────────────────────────────────────────


def load_familiar_results(results_dir):
    """Load familiar session results from multi_session_results.json.

    Returns:
        dict mapping mouse_id → {VISp_accuracy, VISam_accuracy, session_id, ...}
    """
    results_path = Path(results_dir) / "multi_session_results.json"
    if not results_path.exists():
        raise FileNotFoundError(
            f"Familiar results not found at {results_path}. "
            f"Run 05_multi_session.py first."
        )

    with open(results_path) as f:
        data = json.load(f)

    familiar_by_mouse = {}
    for r in data["session_results"]:
        if r.get("status") != "complete":
            continue
        mouse_id = r.get("mouse_id")
        if mouse_id is None:
            continue
        # Normalize mouse_id to int
        mouse_id = int(mouse_id)
        familiar_by_mouse[mouse_id] = {
            "session_id": r["session_id"],
            "VISp_accuracy": r["VISp_accuracy"],
            "VISam_accuracy": r["VISam_accuracy"],
            "VISp_std": r["late_window"]["VISp"]["accuracy_std"],
            "VISam_std": r["late_window"]["VISam"]["accuracy_std"],
            "VISp_units": r["late_window"]["VISp"]["n_units"],
            "VISam_units": r["late_window"]["VISam"]["n_units"],
            "n_omissions": r["late_window"]["VISp"]["n_omission_trials"],
            "genotype": r.get("genotype_short", "unknown"),
        }

    return familiar_by_mouse


# ── Novel session pipeline ──────────────────────────────────────────────────


def run_novel_session(cache, session_id, units_table, spike_dir,
                      n_permutations=100, skip_extraction=False):
    """Extract and decode one novel session. Same pipeline as 05_multi_session.

    Returns:
        dict with per-area accuracies, p-values, unit counts, etc.
    """
    result = {"session_id": int(session_id), "status": "started"}
    t0 = time.time()

    late_data_path = Path(spike_dir) / f"session_{session_id}" / LATE_TAG

    # ── Extraction ──
    if not skip_extraction or not late_data_path.exists():
        print(f"  Extracting 400–750ms window...")
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

    # ── Decoding ──
    print(f"  Decoding (late window, {n_permutations} permutations)...")
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
            "null_distribution": [float(x) for x in null_dist],
            "n_units": n_units,
            "n_omission_trials": n_omit,
        }

    elapsed = time.time() - t0
    result.update({
        "status": "complete",
        "late_window": late_results,
        "elapsed_seconds": round(elapsed, 1),
        "VISp_accuracy": late_results["VISp"]["observed_accuracy"],
        "VISam_accuracy": late_results["VISam"]["observed_accuracy"],
    })

    print(f"  VISp={result['VISp_accuracy']:.3f}, VISam={result['VISam_accuracy']:.3f}")
    print(f"  Completed in {elapsed:.0f}s")

    return result


# ── Analysis ────────────────────────────────────────────────────────────────


def analyze_paired_results(familiar_by_mouse, novel_by_mouse):
    """Compute within-mouse deltas and run statistical tests.

    Returns:
        analysis: dict with all results, deltas, and test statistics
    """
    from scipy import stats

    mice = sorted(set(familiar_by_mouse.keys()) & set(novel_by_mouse.keys()))
    n = len(mice)

    if n < 3:
        return {"n_mice": n, "warning": "too_few_mice"}

    rows = []
    for mid in mice:
        fam = familiar_by_mouse[mid]
        nov = novel_by_mouse[mid]
        rows.append({
            "mouse_id": mid,
            "genotype": fam["genotype"],
            "fam_session": fam["session_id"],
            "nov_session": nov["session_id"],
            # VISp
            "VISp_familiar": fam["VISp_accuracy"],
            "VISp_novel": nov["VISp_accuracy"],
            "VISp_delta": nov["VISp_accuracy"] - fam["VISp_accuracy"],
            "VISp_fam_units": fam["VISp_units"],
            "VISp_nov_units": nov.get("VISp_units", 0),
            # VISam
            "VISam_familiar": fam["VISam_accuracy"],
            "VISam_novel": nov["VISam_accuracy"],
            "VISam_delta": nov["VISam_accuracy"] - fam["VISam_accuracy"],
            "VISam_fam_units": fam["VISam_units"],
            "VISam_nov_units": nov.get("VISam_units", 0),
            # Omissions
            "fam_omissions": fam["n_omissions"],
            "nov_omissions": nov.get("n_omissions", 0),
        })

    df = pd.DataFrame(rows)

    # ── Print the paired table ──
    print(f"\n{'='*100}")
    print(f"WITHIN-MOUSE PAIRED RESULTS (n={n} mice)")
    print(f"{'='*100}")
    print(f"  {'Mouse':>8s}  {'Geno':>8s}  "
          f"{'VISp_Fam':>8s}  {'VISp_Nov':>8s}  {'VISp_Δ':>7s}  "
          f"{'VISam_Fam':>9s}  {'VISam_Nov':>9s}  {'VISam_Δ':>8s}")
    print(f"  {'-'*90}")
    for _, r in df.iterrows():
        print(f"  {r['mouse_id']:>8d}  {r['genotype']:>8s}  "
              f"{r['VISp_familiar']:>8.3f}  {r['VISp_novel']:>8.3f}  "
              f"{r['VISp_delta']:>+7.3f}  "
              f"{r['VISam_familiar']:>9.3f}  {r['VISam_novel']:>9.3f}  "
              f"{r['VISam_delta']:>+8.3f}")

    # ── Statistical tests ──
    visp_deltas = df["VISp_delta"].values
    visam_deltas = df["VISam_delta"].values

    analysis = {"n_mice": n, "mouse_table": rows}

    for area, deltas in [("VISp", visp_deltas), ("VISam", visam_deltas)]:
        mean_d = float(np.mean(deltas))
        std_d = float(np.std(deltas, ddof=1)) if n > 1 else 0.0
        cohens_d = mean_d / std_d if std_d > 0 else 0.0

        # Wilcoxon on familiar vs. novel accuracies
        fam_accs = df[f"{area}_familiar"].values
        nov_accs = df[f"{area}_novel"].values
        if n >= 5:
            w_stat, w_p = stats.wilcoxon(fam_accs, nov_accs, alternative="two-sided")
        else:
            n_drops = int(np.sum(deltas < 0))
            w_stat = float(n_drops)
            w_p = float(stats.binomtest(n_drops, n, 0.5).pvalue)

        # Sign test: how many mice show a drop?
        n_drop = int(np.sum(deltas < 0))
        n_rise = int(np.sum(deltas > 0))
        n_concordant = max(n_drop, n_rise)
        sign_p = float(stats.binomtest(n_concordant, n, 0.5,
                                        alternative="greater").pvalue)

        # Permutation test on deltas
        rng = np.random.default_rng(RANDOM_SEED)
        n_perm = 10000
        perm_means = np.zeros(n_perm)
        for i in range(n_perm):
            signs = rng.choice([-1, 1], size=n)
            perm_means[i] = np.mean(deltas * signs)
        perm_p = float((np.sum(np.abs(perm_means) >= np.abs(mean_d)) + 1) / (n_perm + 1))

        analysis[area] = {
            "mean_familiar": float(np.mean(fam_accs)),
            "mean_novel": float(np.mean(nov_accs)),
            "mean_delta": mean_d,
            "std_delta": std_d,
            "cohens_d": cohens_d,
            "n_drop": n_drop,
            "n_rise": n_rise,
            "wilcoxon_p": float(w_p),
            "sign_test_p": sign_p,
            "permutation_p": perm_p,
        }

        direction = "DROP" if mean_d < 0 else "RISE" if mean_d > 0 else "NO CHANGE"
        print(f"\n  {area}: Familiar → Novel")
        print(f"    Mean familiar: {np.mean(fam_accs):.3f}")
        print(f"    Mean novel:    {np.mean(nov_accs):.3f}")
        print(f"    Mean delta:    {mean_d:+.3f} ({direction})")
        print(f"    Cohen's d:     {cohens_d:.2f}")
        print(f"    Mice showing drop: {n_drop}/{n}, rise: {n_rise}/{n}")
        print(f"    Wilcoxon p:    {w_p:.4f}")
        print(f"    Sign test p:   {sign_p:.4f}")
        print(f"    Permutation p: {perm_p:.4f}")

    # ── Interaction: does the drop differ between areas? ──
    delta_diff = visam_deltas - visp_deltas  # positive = VISam drops less
    mean_dd = float(np.mean(delta_diff))
    if n >= 5:
        inter_stat, inter_p = stats.wilcoxon(visp_deltas, visam_deltas,
                                              alternative="two-sided")
    else:
        inter_p = 1.0
        inter_stat = 0.0

    analysis["interaction"] = {
        "mean_delta_diff_VISam_minus_VISp": mean_dd,
        "wilcoxon_p": float(inter_p),
        "interpretation": (
            "VISam drops LESS than VISp" if mean_dd > 0
            else "VISp drops LESS than VISam" if mean_dd < 0
            else "Equal drops"
        ),
    }

    print(f"\n  Interaction (Area × Experience):")
    print(f"    VISam delta − VISp delta = {mean_dd:+.3f}")
    print(f"    ({analysis['interaction']['interpretation']})")
    print(f"    Wilcoxon p: {inter_p:.4f}")

    return analysis


# ── Visualization ───────────────────────────────────────────────────────────


def plot_paired_novelty(analysis, output_dir):
    """Generate paired slope plots: Familiar → Novel for each area."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skipping plots.")
        return

    rows = analysis["mouse_table"]
    n = len(rows)

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))

    area_colors = {"VISp": "#2196F3", "VISam": "#9C27B0"}

    # ── Panel A & B: Slope plots per area ──
    for ax, area in zip(axes[:2], AREAS):
        color = area_colors[area]
        fam_accs = [r[f"{area}_familiar"] for r in rows]
        nov_accs = [r[f"{area}_novel"] for r in rows]
        mice = [str(r["mouse_id"])[-4:] for r in rows]

        for i in range(n):
            ax.plot([0, 1], [fam_accs[i], nov_accs[i]], "o-",
                    color=color, alpha=0.4, linewidth=1.5, markersize=7)
            # Label mouse on the right
            ax.annotate(mice[i], (1.03, nov_accs[i]),
                        fontsize=7, color="gray", va="center")

        # Means
        mean_fam = np.mean(fam_accs)
        mean_nov = np.mean(nov_accs)
        ax.plot([0, 1], [mean_fam, mean_nov], "D-",
                color=color, linewidth=3, markersize=10, zorder=5,
                label=f"Mean: {mean_fam:.3f} → {mean_nov:.3f}")

        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Familiar", "Novel"], fontsize=12)
        ax.set_ylabel("Decoding accuracy (400–750ms)", fontsize=11)
        ax.set_title(f"{area}", fontsize=14, fontweight="bold", color=color)
        ax.set_xlim(-0.15, 1.25)
        ax.set_ylim(0.45, 1.0)
        ax.axhline(0.5, color="gray", linestyle="--", alpha=0.3)
        ax.legend(fontsize=9, loc="lower left")

        # Add stats annotation
        stats_info = analysis[area]
        delta = stats_info["mean_delta"]
        p_val = min(stats_info["wilcoxon_p"], stats_info["sign_test_p"],
                    stats_info["permutation_p"])
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "n.s."
        ax.text(0.5, 0.47, f"Δ = {delta:+.3f}  {sig}\n(best p = {p_val:.4f})",
                ha="center", fontsize=9, style="italic",
                transform=ax.get_xAxes if False else None)  # placed in data coords
        ax.annotate(f"Δ = {delta:+.3f}  {sig}", xy=(0.5, 0.96),
                    xycoords="axes fraction", ha="center", fontsize=10,
                    fontstyle="italic", color=color)

    # ── Panel C: Delta comparison (VISp delta vs VISam delta) ──
    ax = axes[2]
    visp_deltas = [r["VISp_delta"] for r in rows]
    visam_deltas = [r["VISam_delta"] for r in rows]
    mice = [str(r["mouse_id"])[-4:] for r in rows]

    ax.scatter(visp_deltas, visam_deltas, c="gray", s=60, zorder=3, edgecolors="white")
    for i in range(n):
        ax.annotate(mice[i], (visp_deltas[i] + 0.003, visam_deltas[i] + 0.003),
                    fontsize=7, color="gray")

    # Reference lines
    lims = [min(min(visp_deltas), min(visam_deltas)) - 0.02,
            max(max(visp_deltas), max(visam_deltas)) + 0.02]
    ax.plot(lims, lims, "--", color="gray", alpha=0.5, label="Equal drop")
    ax.axhline(0, color="gray", linewidth=0.5, alpha=0.3)
    ax.axvline(0, color="gray", linewidth=0.5, alpha=0.3)

    ax.set_xlabel("VISp delta (Novel − Familiar)", fontsize=11, color=area_colors["VISp"])
    ax.set_ylabel("VISam delta (Novel − Familiar)", fontsize=11, color=area_colors["VISam"])
    ax.set_title("Area × Experience interaction", fontsize=13)
    ax.legend(fontsize=9)

    inter = analysis["interaction"]
    ax.annotate(f"{inter['interpretation']}\np = {inter['wilcoxon_p']:.4f}",
                xy=(0.05, 0.95), xycoords="axes fraction",
                ha="left", va="top", fontsize=9, fontstyle="italic")

    fig.suptitle(
        f"Within-Mouse Familiar vs. Novel Comparison (n={n} mice)\n"
        f"400–750ms post-stimulus omission decoding",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout()

    out_path = Path(output_dir) / "paired_novelty_results.png"
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"\nSaved figure: {out_path}")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Within-mouse familiar vs. novel omission decoding comparison."
    )
    parser.add_argument(
        "--n_permutations", type=int, default=100,
        help="Permutations per area per session (default: 100).",
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
        "--results_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "multi_session"),
        help="Directory containing multi_session_results.json (familiar baselines).",
    )
    parser.add_argument(
        "--output_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "novelty_comparison"),
        help="Directory for novelty comparison outputs.",
    )
    parser.add_argument(
        "--skip_extraction", action="store_true",
        help="Skip extraction if spike data already exists.",
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Show paired session mapping without processing.",
    )
    args = parser.parse_args()

    # ── Load familiar baselines ──
    print("Loading familiar baselines...")
    familiar_by_mouse = load_familiar_results(args.results_dir)
    print(f"  Found {len(familiar_by_mouse)} familiar sessions with mouse_id")

    # ── Show paired mapping ──
    print(f"\n{'='*80}")
    print(f"PAIRED SESSION MAPPING (9 mice)")
    print(f"{'='*80}")
    print(f"  {'Mouse':>8s}  {'Geno':>8s}  {'Fam Session':>12s}  {'Nov Session':>12s}  "
          f"{'Fam VISp':>8s}  {'Fam VISam':>9s}")
    print(f"  {'-'*70}")

    novel_session_ids = []
    for mouse_id, pair in sorted(PAIRED_SESSIONS.items()):
        fam = familiar_by_mouse.get(mouse_id, {})
        geno = fam.get("genotype", "?")
        fam_vp = fam.get("VISp_accuracy", 0)
        fam_va = fam.get("VISam_accuracy", 0)
        print(f"  {mouse_id:>8d}  {geno:>8s}  {pair['familiar']:>12d}  "
              f"{pair['novel']:>12d}  {fam_vp:>8.3f}  {fam_va:>9.3f}")
        novel_session_ids.append(pair["novel"])

    if args.dry_run:
        print("\n[DRY RUN] Stopping here.")
        return

    # ── Initialize cache ──
    print(f"\nCache: {args.cache_dir}")
    cache = VisualBehaviorNeuropixelsProjectCache.from_s3_cache(
        cache_dir=args.cache_dir
    )
    print("Loading unit table...")
    units_table = cache.get_unit_table()

    # ── Process novel sessions ──
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.spike_dir, exist_ok=True)

    novel_by_mouse = {}
    total_t0 = time.time()

    for i, (mouse_id, pair) in enumerate(sorted(PAIRED_SESSIONS.items())):
        novel_sid = pair["novel"]
        fam = familiar_by_mouse.get(mouse_id, {})
        geno = fam.get("genotype", "?")

        print(f"\n{'='*60}")
        print(f"NOVEL SESSION {i+1}/9: {novel_sid} (mouse {mouse_id}, {geno})")
        print(f"{'='*60}")

        result = run_novel_session(
            cache, novel_sid, units_table,
            spike_dir=args.spike_dir,
            n_permutations=args.n_permutations,
            skip_extraction=args.skip_extraction,
        )

        if result["status"] == "complete":
            novel_by_mouse[mouse_id] = {
                "session_id": novel_sid,
                "VISp_accuracy": result["VISp_accuracy"],
                "VISam_accuracy": result["VISam_accuracy"],
                "VISp_units": result["late_window"]["VISp"]["n_units"],
                "VISam_units": result["late_window"]["VISam"]["n_units"],
                "n_omissions": result["late_window"]["VISp"]["n_omission_trials"],
                "late_window": result["late_window"],
            }
        else:
            print(f"  WARNING: Session {novel_sid} failed: {result['status']}")

        # Interim save
        interim_path = Path(args.output_dir) / "novel_results_interim.json"
        with open(interim_path, "w") as f:
            json.dump({"novel_by_mouse": {str(k): v for k, v in novel_by_mouse.items()}},
                      f, indent=2, default=str)

    total_elapsed = time.time() - total_t0

    # ── Analysis ──
    print(f"\n{'='*60}")
    print(f"PAIRED ANALYSIS")
    print(f"{'='*60}")

    analysis = analyze_paired_results(familiar_by_mouse, novel_by_mouse)

    # ── Save ──
    output = {
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "late_window_ms": list(LATE_WINDOW_MS),
            "late_bin_ms": LATE_BIN_MS,
            "n_permutations": args.n_permutations,
            "n_folds": N_FOLDS,
            "n_undersample_repeats": N_UNDERSAMPLE_REPEATS,
            "random_seed": RANDOM_SEED,
        },
        "paired_sessions": {str(k): v for k, v in PAIRED_SESSIONS.items()},
        "analysis": analysis,
        "novel_results": {str(k): v for k, v in novel_by_mouse.items()},
        "familiar_results": {str(k): v for k, v in familiar_by_mouse.items()},
        "total_elapsed_seconds": round(total_elapsed, 1),
    }

    final_path = Path(args.output_dir) / "paired_novelty_results.json"
    with open(final_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {final_path}")

    # ── Plot ──
    plot_paired_novelty(analysis, args.output_dir)

    # ── Conclusion ──
    print(f"\n{'='*60}")
    print(f"CONCLUSION")
    print(f"{'='*60}")

    if analysis.get("warning"):
        print(f"Insufficient data: {analysis['warning']}")
    else:
        for area in AREAS:
            a = analysis[area]
            direction = "DROPS" if a["mean_delta"] < 0 else "RISES"
            best_p = min(a["wilcoxon_p"], a["sign_test_p"], a["permutation_p"])
            sig = "***" if best_p < 0.001 else "**" if best_p < 0.01 else "*" if best_p < 0.05 else "n.s."
            print(f"  {area}: {a['mean_familiar']:.3f} → {a['mean_novel']:.3f} "
                  f"({direction} {abs(a['mean_delta']):.3f}) {sig}")
            print(f"    Mice: {a['n_drop']} drop, {a['n_rise']} rise")

        inter = analysis["interaction"]
        print(f"\n  Interaction: {inter['interpretation']} "
              f"(p={inter['wilcoxon_p']:.4f})")

        # Interpret the outcome
        visp_drop = analysis["VISp"]["mean_delta"] < -0.05
        visam_drop = analysis["VISam"]["mean_delta"] < -0.05
        visp_stable = abs(analysis["VISp"]["mean_delta"]) < 0.05
        visam_stable = abs(analysis["VISam"]["mean_delta"]) < 0.05

        print(f"\n  INTERPRETATION:")
        if visp_drop and visam_drop:
            print(f"  → Both areas drop: LEARNED PREDICTION signal")
            print(f"    The 400–750ms signal depends on prior image experience")
        elif visp_stable and visam_stable:
            print(f"  → Both areas stable: HARDWIRED V1 DYNAMICS")
            print(f"    The signal is intrinsic, not learned")
        elif visp_drop and visam_stable:
            print(f"  → VISp drops, VISam stable: AREA-SPECIFIC LEARNING")
            print(f"    V1 prediction error depends on learning; VISam is intrinsic")
        elif visam_drop and visp_stable:
            print(f"  → VISam drops, VISp stable: unexpected")
        else:
            print(f"  → Mixed / moderate effects — requires further analysis")

    print(f"\nTotal runtime: {total_elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()