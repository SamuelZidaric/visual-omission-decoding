"""
02_extract_spikes.py
Extract spike times aligned to stimulus onsets, separate omission vs. expected
trials, bin into firing rate vectors, and save clean arrays for decoding.

Processes one session at a time. Outputs per session:
  - firing_rates_{area}.npy: shape (n_trials, n_units, n_bins)
  - labels.npy: 1 = omission, 0 = expected
  - metadata.json: session ID, unit IDs, bin edges, trial counts, area info

Usage:
    python 02_extract_spikes.py --session_id 1064644573
    python 02_extract_spikes.py --session_id 1064644573 --bin_width_ms 50 --window_ms 0 500
    python 02_extract_spikes.py --all --max_sessions 5
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from allensdk.brain_observatory.behavior.behavior_project_cache.behavior_neuropixels_project_cache import (
    VisualBehaviorNeuropixelsProjectCache,
)

# ── Config ──────────────────────────────────────────────────────────────────

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "allen_vbn_cache")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "spike_matrices")
AREAS = ["VISp", "VISam"]
MIN_UNITS_PER_AREA = 20

QUALITY_FILTERS = {
    "isi_violations": 0.5,
    "amplitude_cutoff": 0.1,
    "presence_ratio": 0.95,
}

# Default time window: 0–250ms post-stimulus onset, single bin
DEFAULT_WINDOW_MS = (0, 250)
DEFAULT_BIN_WIDTH_MS = 250  # single bin covering the full window

# Pre-stimulus baseline for optional baseline subtraction
BASELINE_WINDOW_MS = (-250, 0)


# ── Core functions ──────────────────────────────────────────────────────────


def get_quality_unit_ids(units_table, session_id, area):
    """Return unit IDs passing quality filters for a given session and area.

    Args:
        units_table: pre-loaded DataFrame from cache.get_unit_table()
        session_id: ecephys_session_id
        area: structure_acronym (e.g., 'VISp')
    """
    mask = (
        (units_table["ecephys_session_id"] == session_id)
        & (units_table["structure_acronym"] == area)
        & (units_table["isi_violations"] < QUALITY_FILTERS["isi_violations"])
        & (units_table["amplitude_cutoff"] < QUALITY_FILTERS["amplitude_cutoff"])
        & (units_table["presence_ratio"] > QUALITY_FILTERS["presence_ratio"])
    )
    return units_table.loc[mask].index.tolist()


def get_trial_times(session, active_only=False):
    """Extract omission and expected trial onset times from stimulus table.

    In the VBN change detection task, natural images are flashed (250ms on,
    500ms gray) and 5% are omitted. The stimulus_presentations table includes
    all epochs (gabors, flashes, behavior task, passive replay). We filter to
    image presentations from the change detection stream only.

    Args:
        session: Allen VBN session object
        active_only: if True, restrict to active behavior block only.
            Default False keeps both active and passive replay blocks,
            maximizing trial count for decoding.

    Returns:
        omission_times: array of onset times for omitted stimuli
        expected_times: array of onset times for presented (non-omitted) stimuli
        stim_table: filtered stimulus presentations DataFrame
    """
    stim = session.stimulus_presentations

    if "omitted" not in stim.columns:
        raise ValueError(
            f"No 'omitted' column in stimulus_presentations. "
            f"Available columns: {list(stim.columns)}"
        )

    # Keep only image presentations from the change detection task.
    # Exclude: gabors, flashes, spontaneous, optotagging.
    # In VBN, image stimuli have stimulus_name like 'im000_r', 'im036_r', etc.
    # or the omitted flag is True (omissions still have an image_name but
    # weren't shown). The safest approach: exclude known non-task stimuli.
    non_task = {"gabor", "spontaneous", "flash", "natural_movie"}
    task_mask = ~stim["stimulus_name"].apply(
        lambda x: any(nt in str(x).lower() for nt in non_task)
    )
    task_stim = stim[task_mask].copy()

    if active_only and "active" in task_stim.columns:
        task_stim = task_stim[task_stim["active"]].copy()

    # Omission vs. expected
    omission_mask = task_stim["omitted"].astype(bool)

    # For expected trials, exclude change trials — their neural response
    # includes surprise from the image change, confounding the omission
    # comparison. We want "standard" non-change, non-omission flashes.
    if "is_change" in task_stim.columns:
        expected_mask = ~omission_mask & ~task_stim["is_change"].astype(bool)
    else:
        expected_mask = ~omission_mask

    omission_times = task_stim.loc[omission_mask, "start_time"].values
    expected_times = task_stim.loc[expected_mask, "start_time"].values

    print(f"    Stimulus table: {len(stim)} total rows → {len(task_stim)} task stimuli")
    print(f"    Unique stimulus names in task: {sorted(task_stim['stimulus_name'].unique()[:10])}")

    return omission_times, expected_times, task_stim


def bin_spikes(spike_times_dict, unit_ids, trial_onsets, window_s, bin_edges_s):
    """Bin spikes into a trial × unit × time_bin firing rate matrix.

    Args:
        spike_times_dict: dict mapping unit_id → np.array of spike times (s)
        unit_ids: list of unit IDs to include
        trial_onsets: array of trial onset times (s)
        window_s: (start, end) relative to onset in seconds
        bin_edges_s: array of bin edges relative to onset in seconds

    Returns:
        rates: np.array of shape (n_trials, n_units, n_bins), firing rates in Hz
    """
    n_trials = len(trial_onsets)
    n_units = len(unit_ids)
    n_bins = len(bin_edges_s) - 1
    rates = np.zeros((n_trials, n_units, n_bins), dtype=np.float32)

    for u_idx, uid in enumerate(unit_ids):
        spikes = spike_times_dict.get(uid, np.array([]))
        if len(spikes) == 0:
            continue

        for t_idx, onset in enumerate(trial_onsets):
            # Absolute spike times in the trial window
            t_start = onset + window_s[0]
            t_end = onset + window_s[1]

            # Extract spikes in window (searchsorted for speed)
            i_start = np.searchsorted(spikes, t_start)
            i_end = np.searchsorted(spikes, t_end)
            trial_spikes = spikes[i_start:i_end] - onset  # relative to onset

            # Histogram into bins
            counts, _ = np.histogram(trial_spikes, bins=bin_edges_s)

            # Convert to firing rate (Hz): counts / bin_width_in_seconds
            bin_widths = np.diff(bin_edges_s)
            rates[t_idx, u_idx, :] = counts / bin_widths

    return rates


def process_session(cache, session_id, window_ms, bin_width_ms, output_dir,
                    units_table, dry_run=False):
    """Process a single session: extract spikes, bin, save.

    Args:
        cache: VisualBehaviorNeuropixelsProjectCache
        session_id: ecephys_session_id
        window_ms: (start_ms, end_ms) relative to stimulus onset
        bin_width_ms: width of each time bin in ms
        output_dir: directory to save outputs
        dry_run: if True, just report counts without downloading NWB

    Returns:
        dict with summary stats, or None if session is not viable
    """
    # ── 1. Check unit counts per area (metadata only, no NWB download) ──
    area_units = {}
    for area in AREAS:
        uids = get_quality_unit_ids(units_table, session_id, area)
        area_units[area] = uids
        if len(uids) < MIN_UNITS_PER_AREA:
            print(
                f"  Session {session_id}: {area} has {len(uids)} units "
                f"(< {MIN_UNITS_PER_AREA}). Skipping."
            )
            return None

    print(f"  Unit counts: {', '.join(f'{a}={len(u)}' for a, u in area_units.items())}")

    if dry_run:
        return {"session_id": session_id, "unit_counts": {a: len(u) for a, u in area_units.items()}}

    # ── 2. Download session and extract trials ──
    print(f"  Downloading NWB for session {session_id}...")
    session = cache.get_ecephys_session(ecephys_session_id=session_id)
    omission_times, expected_times, stim_table = get_trial_times(session)

    n_omit = len(omission_times)
    n_expected = len(expected_times)
    print(f"  Trials: {n_omit} omissions, {n_expected} expected")

    if n_omit < 50:
        print(f"  WARNING: Only {n_omit} omission trials. May be too few for decoding.")

    # ── 3. Set up time bins ──
    window_s = (window_ms[0] / 1000.0, window_ms[1] / 1000.0)
    bin_width_s = bin_width_ms / 1000.0
    bin_edges_s = np.arange(window_s[0], window_s[1] + 1e-9, bin_width_s)
    n_bins = len(bin_edges_s) - 1

    print(f"  Window: {window_ms[0]}–{window_ms[1]} ms, {n_bins} bin(s) of {bin_width_ms} ms")

    # ── 4. Get spike times ──
    spike_times = session.spike_times

    # ── 5. Combine all trial onsets and create labels ──
    # Labels: 1 = omission, 0 = expected
    all_onsets = np.concatenate([omission_times, expected_times])
    labels = np.concatenate([np.ones(n_omit, dtype=np.int8), np.zeros(n_expected, dtype=np.int8)])

    # Sort by time (keeps temporal order for potential time-aware CV)
    sort_idx = np.argsort(all_onsets)
    all_onsets = all_onsets[sort_idx]
    labels = labels[sort_idx]

    # ── 6. Bin spikes per area ──
    # Include window config in directory name to avoid overwriting different extractions
    window_tag = f"w{window_ms[0]}-{window_ms[1]}ms_b{bin_width_ms}ms"
    session_dir = Path(output_dir) / f"session_{session_id}" / window_tag
    session_dir.mkdir(parents=True, exist_ok=True)

    area_metadata = {}
    for area in AREAS:
        uids = area_units[area]
        print(f"  Binning {area} ({len(uids)} units, {len(all_onsets)} trials)...")
        rates = bin_spikes(spike_times, uids, all_onsets, window_s, bin_edges_s)

        # Save
        np.save(session_dir / f"firing_rates_{area}.npy", rates)
        area_metadata[area] = {
            "unit_ids": [int(u) for u in uids],
            "n_units": len(uids),
            "shape": list(rates.shape),
        }

        # Quick sanity check: mean firing rate across all trials/units/bins
        mean_rate = float(rates.mean())
        print(f"    Mean firing rate: {mean_rate:.1f} Hz")

    # ── 7. Save labels and metadata ──
    np.save(session_dir / "labels.npy", labels)

    metadata = {
        "ecephys_session_id": int(session_id),
        "areas": area_metadata,
        "n_omission_trials": int(n_omit),
        "n_expected_trials": int(n_expected),
        "n_total_trials": int(len(labels)),
        "window_ms": list(window_ms),
        "bin_width_ms": int(bin_width_ms),
        "bin_edges_s": [round(float(e), 6) for e in bin_edges_s],
        "n_bins": n_bins,
        "quality_filters": QUALITY_FILTERS,
    }

    with open(session_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  Saved to {session_dir}")

    # ── 8. Diagnostic PSTH plot ──
    plot_diagnostic_psths(
        spike_times, area_units, omission_times, expected_times, session_dir, session_id
    )

    return metadata


def plot_diagnostic_psths(spike_times, area_units, omission_times, expected_times,
                          output_dir, session_id, n_example_units=3):
    """Plot PSTHs for a few example units to visually verify omission responses.

    Generates one figure per area with n_example_units subplots, each showing
    the average firing rate for omission vs. expected trials in a wide window
    (-250ms to +500ms) at 10ms resolution.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available, skipping diagnostic plots.")
        return

    psth_window_s = (-0.25, 0.5)
    psth_bin_s = 0.01  # 10ms bins
    psth_edges = np.arange(psth_window_s[0], psth_window_s[1] + 1e-9, psth_bin_s)
    psth_centers = psth_edges[:-1] + psth_bin_s / 2

    for area in AREAS:
        uids = area_units[area]
        # Pick units with highest overall firing rate (most informative PSTHs)
        mean_rates = []
        for uid in uids:
            spikes = spike_times.get(uid, np.array([]))
            if len(spikes) > 0:
                # Rough rate estimate
                mean_rates.append(len(spikes) / (spikes[-1] - spikes[0] + 1e-9))
            else:
                mean_rates.append(0.0)
        top_idx = np.argsort(mean_rates)[-n_example_units:]
        example_uids = [uids[i] for i in top_idx]

        fig, axes = plt.subplots(n_example_units, 1, figsize=(8, 3 * n_example_units),
                                 sharex=True)
        if n_example_units == 1:
            axes = [axes]

        for ax, uid in zip(axes, example_uids):
            spikes = spike_times.get(uid, np.array([]))

            for trial_times, label, color in [
                (expected_times, "Expected", "#2196F3"),
                (omission_times, "Omission", "#F44336"),
            ]:
                all_counts = []
                for onset in trial_times:
                    i0 = np.searchsorted(spikes, onset + psth_window_s[0])
                    i1 = np.searchsorted(spikes, onset + psth_window_s[1])
                    rel = spikes[i0:i1] - onset
                    counts, _ = np.histogram(rel, bins=psth_edges)
                    all_counts.append(counts / psth_bin_s)  # Hz

                mean_psth = np.mean(all_counts, axis=0)
                sem_psth = np.std(all_counts, axis=0) / np.sqrt(len(all_counts))

                ax.plot(psth_centers * 1000, mean_psth, color=color, label=label, linewidth=1.5)
                ax.fill_between(psth_centers * 1000, mean_psth - sem_psth,
                                mean_psth + sem_psth, alpha=0.2, color=color)

            ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, label="Stimulus onset")
            ax.axvline(250, color="gray", linestyle=":", linewidth=0.8, label="Stimulus offset")
            ax.set_ylabel("Firing rate (Hz)")
            ax.set_title(f"Unit {uid}", fontsize=10)
            ax.legend(fontsize=8, loc="upper right")

        axes[-1].set_xlabel("Time from stimulus onset (ms)")
        fig.suptitle(f"Session {session_id} — {area} — Diagnostic PSTHs", fontsize=12)
        fig.tight_layout()
        fig.savefig(output_dir / f"psth_diagnostic_{area}.png", dpi=150)
        plt.close(fig)
        print(f"  Saved PSTH diagnostic: {area}")


def get_viable_session_ids(cache):
    """Return session IDs that have both target areas recorded."""
    sessions = cache.get_ecephys_session_table()

    def has_areas(value):
        if isinstance(value, (list, set)):
            areas = list(value)
        elif isinstance(value, str):
            cleaned = value.strip("[]{}").replace("'", "").replace('"', "")
            areas = [a.strip() for a in cleaned.split(",") if a.strip()]
        else:
            areas = []
        return all(a in areas for a in AREAS)

    return sessions[sessions["structure_acronyms"].apply(has_areas)].index.tolist()


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Extract spike data from Allen VBN sessions."
    )
    parser.add_argument(
        "--session_id",
        type=int,
        default=None,
        help="Process a single session by ID.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all viable sessions.",
    )
    parser.add_argument(
        "--max_sessions",
        type=int,
        default=None,
        help="Limit number of sessions to process (use with --all).",
    )
    parser.add_argument(
        "--window_ms",
        type=int,
        nargs=2,
        default=list(DEFAULT_WINDOW_MS),
        metavar=("START", "END"),
        help=f"Time window relative to stimulus onset in ms (default: {DEFAULT_WINDOW_MS}).",
    )
    parser.add_argument(
        "--bin_width_ms",
        type=int,
        default=DEFAULT_BIN_WIDTH_MS,
        help=f"Bin width in ms (default: {DEFAULT_BIN_WIDTH_MS}).",
    )
    parser.add_argument(
        "--cache_dir",
        type=str,
        default=CACHE_DIR,
        help="Path to Allen VBN cache directory.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=OUTPUT_DIR,
        help="Path to output directory.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Check unit counts without downloading NWB files.",
    )
    args = parser.parse_args()

    # Validate args
    if not args.session_id and not args.all:
        parser.error("Specify --session_id or --all.")

    window_ms = tuple(args.window_ms)
    if window_ms[0] >= window_ms[1]:
        parser.error(f"Invalid window: {window_ms}. START must be < END.")

    bin_width_ms = args.bin_width_ms
    window_span = window_ms[1] - window_ms[0]
    if window_span % bin_width_ms != 0:
        parser.error(
            f"Window span ({window_span} ms) must be evenly divisible by "
            f"bin_width_ms ({bin_width_ms} ms)."
        )

    # Initialize cache
    print(f"Cache directory: {args.cache_dir}")
    cache = VisualBehaviorNeuropixelsProjectCache.from_s3_cache(cache_dir=args.cache_dir)

    print("Loading unit table (one-time)...")
    units_table = cache.get_unit_table()

    # Determine which sessions to process
    if args.session_id:
        session_ids = [args.session_id]
    else:
        session_ids = get_viable_session_ids(cache)
        print(f"Found {len(session_ids)} sessions with {' + '.join(AREAS)}")
        if args.max_sessions:
            session_ids = session_ids[: args.max_sessions]
            print(f"Processing first {len(session_ids)} sessions.")

    # Process
    os.makedirs(args.output_dir, exist_ok=True)
    results = []
    for i, sid in enumerate(session_ids):
        print(f"\n[{i + 1}/{len(session_ids)}] Session {sid}")
        try:
            result = process_session(
                cache, sid, window_ms, bin_width_ms, args.output_dir,
                units_table, dry_run=args.dry_run
            )
            if result:
                results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Processed {len(results)}/{len(session_ids)} sessions successfully.")
    if results and not args.dry_run:
        omit_counts = [r["n_omission_trials"] for r in results]
        print(f"Omission trials per session: {np.min(omit_counts)}–{np.max(omit_counts)} "
              f"(median {np.median(omit_counts):.0f})")


if __name__ == "__main__":
    main()