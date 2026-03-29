"""
01_check_feasibility.py
Query Allen VBN metadata to validate dataset viability.
Checks: session count, unit counts per area, omission trial count.

Run once. If numbers pass thresholds, proceed to Phase 2.
"""

import os
import pandas as pd
from allensdk.brain_observatory.behavior.behavior_project_cache.behavior_neuropixels_project_cache import (
    VisualBehaviorNeuropixelsProjectCache,
)

# --- Config ---
CACHE_DIR = os.path.join(os.getcwd(), "..", "allen_vbn_cache")
MIN_UNITS_PER_AREA = 20
AREAS = ["VISp", "VISam"]

QUALITY_FILTERS = {
    "isi_violations": 0.5,
    "amplitude_cutoff": 0.1,
    "presence_ratio": 0.95,
}


def parse_areas(value):
    """Extract area list from structure_acronyms, handling list, set, or string."""
    if isinstance(value, (list, set)):
        return list(value)
    elif isinstance(value, str):
        cleaned = value.strip("[]{}").replace("'", "").replace('"', "")
        return [a.strip() for a in cleaned.split(",") if a.strip()]
    return []


def has_areas(value, areas):
    """Check if all target areas are present."""
    parsed = parse_areas(value)
    return all(a in parsed for a in areas)


def main():
    cache = VisualBehaviorNeuropixelsProjectCache.from_s3_cache(cache_dir=CACHE_DIR)
    print("Loading session and unit metadata...")
    sessions = cache.get_ecephys_session_table()
    units = cache.get_unit_table()

    # Diagnostic: show what structure_acronyms actually looks like
    sample = sessions["structure_acronyms"].iloc[0]
    print(f"\nstructure_acronyms sample: {repr(sample)}")
    print(f"Type: {type(sample).__name__}")

    # Sessions with both target areas
    sessions_with_both = sessions[
        sessions["structure_acronyms"].apply(lambda x: has_areas(x, AREAS))
    ]
    n_sessions = len(sessions_with_both)
    print(f"\nSessions with simultaneous {' + '.join(AREAS)}: {n_sessions}")

    if n_sessions == 0:
        # Fallback: show all areas found so we can debug naming
        all_areas = set()
        for val in sessions["structure_acronyms"]:
            all_areas.update(parse_areas(val))
        print(f"All areas found across sessions: {sorted(all_areas)}")
        print("\nCheck if target area names match the above list.")
        return

    # Quality-filtered units
    good_units = units[
        (units["isi_violations"] < QUALITY_FILTERS["isi_violations"])
        & (units["amplitude_cutoff"] < QUALITY_FILTERS["amplitude_cutoff"])
        & (units["presence_ratio"] > QUALITY_FILTERS["presence_ratio"])
    ]

    # Unit counts per area per session
    session_ids = sessions_with_both.index.tolist()
    relevant = good_units[good_units["ecephys_session_id"].isin(session_ids)]
    counts = (
        relevant.groupby(["ecephys_session_id", "structure_acronym"])
        .size()
        .unstack(fill_value=0)
    )

    available = [a for a in AREAS if a in counts.columns]
    if not available:
        print("\nNo quality units found in target areas. Check filters.")
        return

    area_counts = counts[available]
    print(f"\nHigh-quality unit counts per session:")
    print(area_counts.describe().round(1))

    # Sessions meeting minimum unit threshold
    viable = area_counts[(area_counts[available] >= MIN_UNITS_PER_AREA).all(axis=1)]
    print(f"\nSessions with >= {MIN_UNITS_PER_AREA} units in both areas: {len(viable)}")

    # Check omission trials for one session
    if not viable.empty:
        test_id = viable.index[0]
        print(f"\nDownloading stimulus table for session {test_id}...")
        print("(This downloads the full NWB file, ~3.5 GB. Be patient.)")
        session_data = cache.get_ecephys_session(ecephys_session_id=test_id)
        stim = session_data.stimulus_presentations

        if "omitted" in stim.columns:
            n_omit = int(stim["omitted"].sum())
            n_std = int((~stim["omitted"]).sum())
            print(f"Standard flashes: {n_std}")
            print(f"Omission trials:  {n_omit}")
            print(f"Omission rate:    {n_omit / len(stim) * 100:.1f}%")
        else:
            print(f"Available columns: {list(stim.columns)}")
            print("WARNING: No 'omitted' column found.")
    else:
        print("\nNo viable sessions. Consider relaxing quality filters or MIN_UNITS_PER_AREA.")


if __name__ == "__main__":
    main()