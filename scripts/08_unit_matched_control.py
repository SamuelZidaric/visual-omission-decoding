"""
08_unit_matched_control.py
Control analysis: does VISp > VISam survive when unit counts are equalized?

For each session, downsamples the area with more units to match the area with
fewer units, re-runs decoding 20 times, and reports mean accuracy. If VISp
still beats VISam, the finding is not a feature-count artifact.

Uses the same 400–750ms window and decoder parameters as 05_multi_session.py.

Usage:
    python 08_unit_matched_control.py
    python 08_unit_matched_control.py --n_subsamples 50  # more stable estimate
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from importlib.util import spec_from_file_location, module_from_spec


def _import_module(name, path):
    spec = spec_from_file_location(name, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


decode_mod = _import_module("decode", SCRIPT_DIR / "04_decode.py")
load_session_data = decode_mod.load_session_data
decode_with_undersampling = decode_mod.decode_with_undersampling

# ── Config ──────────────────────────────────────────────────────────────────

AREAS = ["VISp", "VISam"]
LATE_TAG = "w400-750ms_b350ms"
N_FOLDS = 5
N_UNDERSAMPLE_REPEATS = 10
RANDOM_SEED = 42

# All 10 sessions from multi-session validation
SESSION_IDS = [
    1115077618, 1111013640, 1119946360, 1115086689, 1116941914,
    1108334384, 1152632711, 1099598937, 1067588044, 1139846596,
]


def decode_with_unit_subsample(rates, labels, n_units_target, n_subsamples=20,
                                n_undersample_repeats=N_UNDERSAMPLE_REPEATS,
                                n_folds=N_FOLDS, seed=RANDOM_SEED):
    """Decode after randomly subsampling units to a target count.

    Args:
        rates: (n_trials, n_units, n_bins) firing rate array
        labels: (n_trials,) binary labels
        n_units_target: number of units to subsample to
        n_subsamples: number of random unit subsamples to average over
        n_undersample_repeats: passed to decode_with_undersampling
        n_folds: CV folds
        seed: random seed

    Returns:
        mean_accuracy: mean across all subsamples
        subsample_accuracies: list of per-subsample accuracies
    """
    n_units_total = rates.shape[1]
    rng = np.random.default_rng(seed)

    if n_units_target >= n_units_total:
        # No subsampling needed — just decode normally
        acc, _ = decode_with_undersampling(
            rates, labels,
            n_repeats=n_undersample_repeats,
            n_folds=n_folds,
            seed=seed,
        )
        return float(acc), [float(acc)]

    subsample_accs = []
    for i in range(n_subsamples):
        # Random subset of units
        unit_idx = rng.choice(n_units_total, size=n_units_target, replace=False)
        unit_idx.sort()
        rates_sub = rates[:, unit_idx, :]

        acc, _ = decode_with_undersampling(
            rates_sub, labels,
            n_repeats=n_undersample_repeats,
            n_folds=n_folds,
            seed=seed + i,  # vary seed per subsample for independence
        )
        subsample_accs.append(float(acc))

    return float(np.mean(subsample_accs)), subsample_accs


def main():
    parser = argparse.ArgumentParser(
        description="Unit-matched control: equalize unit counts between VISp and VISam."
    )
    parser.add_argument(
        "--spike_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "spike_matrices"),
    )
    parser.add_argument(
        "--output_dir", type=str,
        default=os.path.join(os.path.dirname(__file__), "..", "results", "unit_matched_control"),
    )
    parser.add_argument(
        "--n_subsamples", type=int, default=20,
        help="Random unit subsamples per session (default: 20).",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    results = []
    total_t0 = time.time()

    for sid in SESSION_IDS:
        print(f"\nSession {sid}...")

        # Load both areas
        area_data = {}
        for area in AREAS:
            try:
                rates, labels, metadata = load_session_data(
                    args.spike_dir, sid, LATE_TAG, area
                )
                area_data[area] = {"rates": rates, "labels": labels, "n_units": rates.shape[1]}
            except FileNotFoundError as e:
                print(f"  Missing data for {area}: {e}")
                break

        if len(area_data) < 2:
            continue

        n_visp = area_data["VISp"]["n_units"]
        n_visam = area_data["VISam"]["n_units"]
        n_matched = min(n_visp, n_visam)

        print(f"  VISp: {n_visp} units, VISam: {n_visam} units → matching to {n_matched}")

        # Original (unmatched) decoding for reference
        orig = {}
        for area in AREAS:
            acc, _ = decode_with_undersampling(
                area_data[area]["rates"], area_data[area]["labels"],
                n_repeats=N_UNDERSAMPLE_REPEATS,
                n_folds=N_FOLDS,
                seed=RANDOM_SEED,
            )
            orig[area] = float(acc)

        # Unit-matched decoding
        matched = {}
        matched_details = {}
        for area in AREAS:
            acc, sub_accs = decode_with_unit_subsample(
                area_data[area]["rates"], area_data[area]["labels"],
                n_units_target=n_matched,
                n_subsamples=args.n_subsamples,
                seed=RANDOM_SEED,
            )
            matched[area] = acc
            matched_details[area] = {
                "mean": acc,
                "std": float(np.std(sub_accs)),
                "min": float(np.min(sub_accs)),
                "max": float(np.max(sub_accs)),
                "subsample_accuracies": sub_accs,
            }

        visp_still_better = matched["VISp"] > matched["VISam"]
        diff_orig = orig["VISam"] - orig["VISp"]
        diff_matched = matched["VISam"] - matched["VISp"]

        result = {
            "session_id": sid,
            "n_visp_orig": n_visp,
            "n_visam_orig": n_visam,
            "n_matched": n_matched,
            "VISp_orig": orig["VISp"],
            "VISam_orig": orig["VISam"],
            "diff_orig": diff_orig,
            "VISp_matched": matched["VISp"],
            "VISam_matched": matched["VISam"],
            "diff_matched": diff_matched,
            "VISp_still_better": visp_still_better,
            "details": matched_details,
        }
        results.append(result)

        marker = "✓" if visp_still_better else "✗"
        print(f"  Original:  VISp={orig['VISp']:.3f}, VISam={orig['VISam']:.3f}, "
              f"diff={diff_orig:+.3f}")
        print(f"  Matched({n_matched}): VISp={matched['VISp']:.3f}, "
              f"VISam={matched['VISam']:.3f}, diff={diff_matched:+.3f}  {marker}")

    total_elapsed = time.time() - total_t0

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"UNIT-MATCHED CONTROL SUMMARY (n={len(results)} sessions)")
    print(f"{'='*70}")

    print(f"\n{'Session':>12s}  {'VISp_n':>6s}  {'VISam_n':>7s}  {'Match':>5s}  "
          f"{'VISp_orig':>9s}  {'VISp_match':>10s}  "
          f"{'VISam_orig':>10s}  {'VISam_match':>11s}  {'Still?':>6s}")
    print(f"{'-'*85}")

    n_still_better = 0
    for r in results:
        marker = "YES" if r["VISp_still_better"] else "NO"
        if r["VISp_still_better"]:
            n_still_better += 1
        print(f"{r['session_id']:>12d}  {r['n_visp_orig']:>6d}  {r['n_visam_orig']:>7d}  "
              f"{r['n_matched']:>5d}  "
              f"{r['VISp_orig']:>9.3f}  {r['VISp_matched']:>10.3f}  "
              f"{r['VISam_orig']:>10.3f}  {r['VISam_matched']:>11.3f}  {marker:>6s}")

    # Paired stats on matched accuracies
    from scipy import stats

    visp_matched = np.array([r["VISp_matched"] for r in results])
    visam_matched = np.array([r["VISam_matched"] for r in results])
    diffs = visam_matched - visp_matched
    n = len(results)

    if n >= 5:
        w_stat, w_p = stats.wilcoxon(visp_matched, visam_matched, alternative="two-sided")
    else:
        w_p = 1.0

    n_concordant = max(n_still_better, n - n_still_better)
    sign_p = float(stats.binomtest(n_concordant, n, 0.5, alternative="greater").pvalue)

    d_mean = np.mean(diffs)
    d_std = np.std(diffs, ddof=1)
    cohens_d = d_mean / d_std if d_std > 0 else 0.0

    print(f"\nVISp still better in {n_still_better}/{n} sessions after unit matching")
    print(f"Matched VISp mean: {np.mean(visp_matched):.3f} ± {np.std(visp_matched):.3f}")
    print(f"Matched VISam mean: {np.mean(visam_matched):.3f} ± {np.std(visam_matched):.3f}")
    print(f"Mean diff (matched): {d_mean:+.3f}")
    print(f"Cohen's d (matched): {cohens_d:.2f}")
    print(f"Wilcoxon p (matched): {w_p:.4f}")
    print(f"Sign test p: {sign_p:.4f}")

    if n_still_better == n:
        print(f"\nCONCLUSION: VISp > VISam survives unit matching in ALL {n} sessions.")
        print(f"The finding is NOT a feature-count artifact.")
    elif n_still_better > n / 2:
        print(f"\nCONCLUSION: VISp > VISam survives in {n_still_better}/{n} sessions.")
        print(f"Effect is attenuated but direction holds.")
    else:
        print(f"\nWARNING: VISp advantage does not survive unit matching.")

    # ── Save ──
    output = {
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "late_tag": LATE_TAG,
            "n_subsamples": args.n_subsamples,
            "n_folds": N_FOLDS,
            "n_undersample_repeats": N_UNDERSAMPLE_REPEATS,
            "random_seed": RANDOM_SEED,
        },
        "summary": {
            "n_sessions": n,
            "n_visp_still_better": n_still_better,
            "mean_visp_matched": float(np.mean(visp_matched)),
            "mean_visam_matched": float(np.mean(visam_matched)),
            "mean_diff_matched": float(d_mean),
            "cohens_d_matched": cohens_d,
            "wilcoxon_p": float(w_p),
            "sign_test_p": sign_p,
        },
        "session_results": results,
        "total_elapsed_seconds": round(total_elapsed, 1),
    }

    out_path = Path(args.output_dir) / "unit_matched_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")
    print(f"Runtime: {total_elapsed:.0f}s")


if __name__ == "__main__":
    main()