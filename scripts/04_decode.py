"""
03_decode.py
Binary decoder: omission vs. expected trials from population firing rates.
Tests H3: is decoding accuracy higher in VISam than VISp?

Pipeline per area:
  1. Load firing rates and labels
  2. Undersample expected trials to balance classes
  3. Flatten features (units × bins → single vector per trial)
  4. Logistic regression (L2, CV-tuned C) with stratified K-fold CV
  5. Permutation test (1,000 shuffles) → null distribution
  6. Compare VISp vs. VISam accuracy

Modes:
  --mode late_window    Primary H3 analysis on 200–400ms single-bin data
  --mode time_resolved  Time-resolved decoding across 50ms bins (0–500ms)
  --mode both           Run both analyses (default)

Usage:
    python 03_decode.py --session_id 1064644573 --data_dir ../results/spike_matrices
    python 03_decode.py --session_id 1064644573 --mode time_resolved
    python 03_decode.py --session_id 1064644573 --mode both --n_permutations 100
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

# ── Config defaults ─────────────────────────────────────────────────────────

AREAS = ["VISp", "VISam"]
N_PERMUTATIONS = 1000
N_FOLDS = 5
RANDOM_SEED = 42
N_UNDERSAMPLE_REPEATS = 10

DEFAULT_LATE_TAG = "w200-400ms_b200ms"
DEFAULT_TR_TAG = "w0-500ms_b50ms"


# ── Core functions ──────────────────────────────────────────────────────────


def load_session_data(data_dir, session_id, window_tag, area):
    """Load firing rates, labels, and metadata for one session/area/window.

    Returns:
        rates: np.array (n_trials, n_units, n_bins)
        labels: np.array (n_trials,) — 1=omission, 0=expected
        metadata: dict
    """
    session_dir = Path(data_dir) / f"session_{session_id}" / window_tag

    rates = np.load(session_dir / f"firing_rates_{area}.npy")
    labels = np.load(session_dir / "labels.npy")

    with open(session_dir / "metadata.json") as f:
        metadata = json.load(f)

    return rates, labels, metadata


def undersample_and_build_X_y(rates, labels, rng):
    """Balance classes by undersampling expected trials, then flatten features.

    Args:
        rates: (n_trials, n_units, n_bins)
        labels: (n_trials,)
        rng: numpy random generator

    Returns:
        X: (n_balanced, n_features) where n_features = n_units * n_bins
        y: (n_balanced,) — balanced labels
    """
    omission_idx = np.where(labels == 1)[0]
    expected_idx = np.where(labels == 0)[0]
    n_omit = len(omission_idx)

    subsample_idx = rng.choice(expected_idx, size=n_omit, replace=False)

    balanced_idx = np.concatenate([omission_idx, subsample_idx])
    rng.shuffle(balanced_idx)

    X = rates[balanced_idx].reshape(len(balanced_idx), -1)
    y = labels[balanced_idx]

    return X, y


def decode_cv(X, y, n_folds=N_FOLDS, rng_seed=None):
    """Logistic regression with stratified K-fold CV and automatic C tuning.

    Uses LogisticRegressionCV to find optimal regularization strength via
    nested cross-validation. Important when n_features (~50 units) is
    comparable to n_trials (~356 per class).

    Returns:
        mean_accuracy: mean accuracy across outer folds
        fold_accuracies: list of per-fold accuracies
    """
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True,
                         random_state=rng_seed)

    fold_accs = []
    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        clf = LogisticRegressionCV(
            Cs=10,
            penalty="l2",
            solver="lbfgs",
            cv=3,
            max_iter=1000,
            random_state=rng_seed,
        )
        clf.fit(X_train, y_train)
        fold_accs.append(clf.score(X_test, y_test))

    return np.mean(fold_accs), fold_accs


def decode_with_undersampling(rates, labels, n_repeats=N_UNDERSAMPLE_REPEATS,
                               n_folds=N_FOLDS, seed=RANDOM_SEED):
    """Run decoding with repeated undersampling to stabilize the estimate.

    Each repeat draws a fresh random subsample of expected trials,
    then runs stratified K-fold CV. Variance is computed across repeat
    means (not individual folds), since folds within a single CV share
    training data and are correlated.

    Returns:
        mean_accuracy: mean of per-repeat means
        repeat_means: list of mean accuracies per repeat (length n_repeats)
    """
    rng = np.random.default_rng(seed)
    repeat_means = []

    for i in range(n_repeats):
        X, y = undersample_and_build_X_y(rates, labels, rng)
        mean_acc, _ = decode_cv(X, y, n_folds=n_folds,
                                rng_seed=rng.integers(1e9))
        repeat_means.append(mean_acc)

    return np.mean(repeat_means), repeat_means


def permutation_test(rates, labels, n_permutations=N_PERMUTATIONS,
                     n_folds=N_FOLDS, seed=RANDOM_SEED):
    """Build null distribution by shuffling labels on a fixed balanced dataset.

    Efficient strategy:
      1. Undersample once to create a fixed balanced X, y
      2. For each permutation, shuffle only y and run K-fold CV
    This avoids redundant re-undersampling and isolates what the null
    actually tests: whether the label-to-activity mapping matters.

    Returns:
        null_distribution: array of shape (n_permutations,)
    """
    rng = np.random.default_rng(seed)

    X_fixed, y_fixed = undersample_and_build_X_y(rates, labels, rng)

    null_dist = np.zeros(n_permutations)

    for p in range(n_permutations):
        y_shuffled = y_fixed.copy()
        rng.shuffle(y_shuffled)

        mean_acc, _ = decode_cv(X_fixed, y_shuffled, n_folds=n_folds,
                                rng_seed=rng.integers(1e9))
        null_dist[p] = mean_acc

        if (p + 1) % 100 == 0:
            print(f"      Permutation {p + 1}/{n_permutations} "
                  f"(null mean so far: {null_dist[:p+1].mean():.3f})")

    return null_dist


def compute_p_value(observed, null_distribution):
    """One-sided p-value: proportion of null >= observed, with pseudo-count."""
    return (np.sum(null_distribution >= observed) + 1) / (len(null_distribution) + 1)


# ── Late-window analysis (H3 primary test) ──────────────────────────────────


def run_late_window(data_dir, session_id, late_tag, n_permutations):
    """Primary H3 analysis: decode omission vs. expected from late-window activity."""
    print(f"\n{'='*60}")
    print(f"LATE-WINDOW ANALYSIS (H3) — Session {session_id}")
    print(f"Tag: {late_tag}")
    print(f"{'='*60}")

    results = {}

    for area in AREAS:
        print(f"\n  ── {area} ──")
        rates, labels, metadata = load_session_data(
            data_dir, session_id, late_tag, area
        )

        n_omit = int(np.sum(labels == 1))
        n_expected = int(np.sum(labels == 0))
        n_units = rates.shape[1]
        n_bins = rates.shape[2]
        n_features = n_units * n_bins
        print(f"  Trials: {n_omit} omission, {n_expected} expected")
        print(f"  Units: {n_units}, Bins: {n_bins}, Features: {n_features}")
        print(f"  Balanced dataset: {n_omit * 2} trials ({n_omit} per class)")

        print(f"  Decoding ({N_UNDERSAMPLE_REPEATS} repeats × {N_FOLDS}-fold CV)...")
        observed_acc, repeat_means = decode_with_undersampling(rates, labels)
        acc_std = np.std(repeat_means)
        print(f"  Observed accuracy: {observed_acc:.3f} "
              f"(±{acc_std:.3f} across {N_UNDERSAMPLE_REPEATS} repeats)")

        print(f"  Running {n_permutations} permutations...")
        null_dist = permutation_test(rates, labels, n_permutations=n_permutations)

        p_value = compute_p_value(observed_acc, null_dist)
        print(f"  Null distribution: mean={null_dist.mean():.3f}, "
              f"std={null_dist.std():.3f}")
        print(f"  p-value: {p_value:.4f}")
        print(f"  Significant (p<0.01): {'YES' if p_value < 0.01 else 'NO'}")

        results[area] = {
            "observed_accuracy": float(observed_acc),
            "accuracy_std_across_repeats": float(acc_std),
            "repeat_means": [float(a) for a in repeat_means],
            "null_mean": float(null_dist.mean()),
            "null_std": float(null_dist.std()),
            "null_95th": float(np.percentile(null_dist, 95)),
            "null_99th": float(np.percentile(null_dist, 99)),
            "p_value": float(p_value),
            "n_permutations": n_permutations,
            "n_units": n_units,
            "n_features": n_features,
            "n_omission_trials": n_omit,
            "null_distribution": [float(x) for x in null_dist],
        }

    # Compare
    print(f"\n  ── Comparison ──")
    for area in AREAS:
        r = results[area]
        sig = "***" if r["p_value"] < 0.01 else ("*" if r["p_value"] < 0.05 else "n.s.")
        print(f"  {area}: {r['observed_accuracy']:.3f} "
              f"(±{r['accuracy_std_across_repeats']:.3f}, "
              f"p={r['p_value']:.4f}) {sig}")

    diff = results["VISam"]["observed_accuracy"] - results["VISp"]["observed_accuracy"]
    print(f"\n  VISam − VISp = {diff:+.3f}")
    if diff > 0:
        print(f"  → VISam decodes BETTER (consistent with H3)")
    elif diff < 0:
        print(f"  → VISp decodes BETTER (opposite to H3)")
    else:
        print(f"  → No difference")

    return results


# ── Time-resolved analysis ──────────────────────────────────────────────────


def run_time_resolved(data_dir, session_id, tr_tag):
    """Slide the decoder across time bins to find when decoding emerges."""
    print(f"\n{'='*60}")
    print(f"TIME-RESOLVED ANALYSIS — Session {session_id}")
    print(f"Tag: {tr_tag}")
    print(f"{'='*60}")

    results = {}

    for area in AREAS:
        print(f"\n  ── {area} ──")
        rates, labels, metadata = load_session_data(
            data_dir, session_id, tr_tag, area
        )

        n_bins = rates.shape[2]
        bin_edges = metadata["bin_edges_s"]
        bin_centers_ms = [
            (bin_edges[i] + bin_edges[i + 1]) / 2 * 1000
            for i in range(n_bins)
        ]

        print(f"  {n_bins} bins, centers: {[f'{c:.0f}ms' for c in bin_centers_ms]}")

        bin_results = []
        for b in range(n_bins):
            rates_bin = rates[:, :, b:b+1]

            acc, repeat_means = decode_with_undersampling(
                rates_bin, labels,
                n_repeats=N_UNDERSAMPLE_REPEATS,
                n_folds=N_FOLDS,
            )
            acc_std = np.std(repeat_means)

            bin_results.append({
                "bin_index": b,
                "bin_center_ms": float(bin_centers_ms[b]),
                "accuracy": float(acc),
                "accuracy_std": float(acc_std),
                "repeat_means": [float(a) for a in repeat_means],
            })

            print(f"    Bin {bin_centers_ms[b]:5.0f}ms: "
                  f"accuracy={acc:.3f} ±{acc_std:.3f}")

        results[area] = bin_results

    print(f"\n  ── Summary ──")
    print(f"  Chance level: 0.500")
    for area in AREAS:
        accs = [b["accuracy"] for b in results[area]]
        peak_bin = results[area][np.argmax(accs)]
        print(f"  {area}: peak accuracy {max(accs):.3f} "
              f"at {peak_bin['bin_center_ms']:.0f}ms")

    return results


# ── Save & plot ─────────────────────────────────────────────────────────────


def save_results(results, output_path, analysis_type, n_permutations=None):
    """Save results to JSON with full parameter provenance."""
    output = {
        "analysis_type": analysis_type,
        "parameters": {
            "n_permutations": n_permutations,
            "n_folds": N_FOLDS,
            "n_undersample_repeats": N_UNDERSAMPLE_REPEATS,
            "random_seed": RANDOM_SEED,
            "classifier": "LogisticRegressionCV(Cs=10, penalty=l2, inner_cv=3)",
            "variance_reported": "std across undersample repeats (not folds)",
        },
        "results": results,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to {output_path}")


def plot_late_window_results(results, output_path, session_id):
    """Plot null distributions with observed accuracy for each area."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available, skipping plots.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    colors = {"VISp": "#2196F3", "VISam": "#9C27B0"}

    for ax, area in zip(axes, AREAS):
        r = results[area]
        null = np.array(r["null_distribution"])
        observed = r["observed_accuracy"]
        p_val = r["p_value"]

        ax.hist(null, bins=40, color=colors[area], alpha=0.5,
                edgecolor="white", linewidth=0.5, label="Null distribution")
        ax.axvline(observed, color=colors[area], linewidth=2.5,
                   linestyle="-", label=f"Observed: {observed:.3f}")
        ax.axvline(r["null_99th"], color="gray", linewidth=1,
                   linestyle="--", label=f"99th pctile: {r['null_99th']:.3f}")

        sig_label = f"p={p_val:.4f}"
        if p_val < 0.01:
            sig_label += " ***"
        elif p_val < 0.05:
            sig_label += " *"

        ax.set_title(f"{area} — {sig_label}", fontsize=13)
        ax.set_xlabel("Decoding accuracy")
        ax.legend(fontsize=9, loc="upper left")

    axes[0].set_ylabel("Count (permutations)")
    fig.suptitle(
        f"Session {session_id} — Omission vs. Expected Decoding (late window)",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"  Saved null distribution plot: {output_path}")


def plot_time_resolved_results(results, output_path, session_id):
    """Plot decoding accuracy vs. time for both areas."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available, skipping plots.")
        return

    colors = {"VISp": "#2196F3", "VISam": "#9C27B0"}
    fig, ax = plt.subplots(figsize=(10, 5))

    for area in AREAS:
        centers = np.array([b["bin_center_ms"] for b in results[area]])
        accs = np.array([b["accuracy"] for b in results[area]])
        stds = np.array([b["accuracy_std"] for b in results[area]])

        ax.plot(centers, accs, "o-", color=colors[area], linewidth=2,
                markersize=6, label=area)
        ax.fill_between(centers, accs - stds, accs + stds,
                        alpha=0.15, color=colors[area])

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="Chance")
    ax.axvline(200, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.axvline(400, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.axvspan(200, 400, alpha=0.05, color="gray", label="Late window (H3)")

    ax.set_xlabel("Time from stimulus onset (ms)", fontsize=12)
    ax.set_ylabel("Decoding accuracy", fontsize=12)
    ax.set_title(
        f"Session {session_id} — Time-Resolved Omission Decoding",
        fontsize=14,
    )
    ax.legend(fontsize=10)
    ax.set_ylim(0.4, 1.0)
    ax.set_xlim(-10, 510)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"  Saved time-resolved plot: {output_path}")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Decode omission vs. expected trials from population activity."
    )
    parser.add_argument(
        "--session_id", type=int, required=True,
        help="Session ID to decode.",
    )
    parser.add_argument(
        "--data_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "spike_matrices"),
        help="Path to spike_matrices directory.",
    )
    parser.add_argument(
        "--output_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "decoding"),
        help="Path to save decoding results.",
    )
    parser.add_argument(
        "--mode", type=str, default="both",
        choices=["late_window", "time_resolved", "both"],
        help="Which analysis to run (default: both).",
    )
    parser.add_argument(
        "--n_permutations", type=int, default=N_PERMUTATIONS,
        help=f"Number of permutations (default: {N_PERMUTATIONS}).",
    )
    parser.add_argument(
        "--late_tag", type=str, default=DEFAULT_LATE_TAG,
        help=f"Directory tag for late-window data (default: {DEFAULT_LATE_TAG}).",
    )
    parser.add_argument(
        "--tr_tag", type=str, default=DEFAULT_TR_TAG,
        help=f"Directory tag for time-resolved data (default: {DEFAULT_TR_TAG}).",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir) / f"session_{args.session_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode in ("late_window", "both"):
        check_path = Path(args.data_dir) / f"session_{args.session_id}" / args.late_tag
        if not check_path.exists():
            print(f"ERROR: Late-window data not found at {check_path}")
            print(f"Run: python 02_extract_spikes.py --session_id {args.session_id} "
                  f"--window_ms 200 400 --bin_width_ms 200")
            sys.exit(1)

        late_results = run_late_window(
            args.data_dir, args.session_id, args.late_tag, args.n_permutations
        )

        late_out = out_dir / args.late_tag
        late_out.mkdir(parents=True, exist_ok=True)
        save_results(
            late_results, late_out / "late_window_results.json",
            "late_window_H3", n_permutations=args.n_permutations
        )
        plot_late_window_results(
            late_results, late_out / "null_distributions.png", args.session_id
        )

    if args.mode in ("time_resolved", "both"):
        check_path = Path(args.data_dir) / f"session_{args.session_id}" / args.tr_tag
        if not check_path.exists():
            print(f"ERROR: Time-resolved data not found at {check_path}")
            print(f"Run: python 02_extract_spikes.py --session_id {args.session_id} "
                  f"--window_ms 0 500 --bin_width_ms 50")
            sys.exit(1)

        tr_results = run_time_resolved(
            args.data_dir, args.session_id, args.tr_tag
        )

        tr_out = out_dir / args.tr_tag
        tr_out.mkdir(parents=True, exist_ok=True)
        save_results(
            tr_results, tr_out / "time_resolved_results.json", "time_resolved"
        )
        plot_time_resolved_results(
            tr_results, tr_out / "time_resolved_accuracy.png", args.session_id
        )

    print(f"\n{'='*60}")
    print(f"All results saved to {out_dir}")


if __name__ == "__main__":
    main()