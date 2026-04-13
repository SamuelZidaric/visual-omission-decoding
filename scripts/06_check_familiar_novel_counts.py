"""
check_novel_sessions.py
Find sessions with novel image exposure that also have VISp + VISam coverage.
Determines if the familiar vs. novel comparison is feasible.

Usage:
    python check_novel_sessions.py --cache_dir .\allen_vbn_cache
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np
from allensdk.brain_observatory.behavior.behavior_project_cache.behavior_neuropixels_project_cache import (
    VisualBehaviorNeuropixelsProjectCache,
)

AREAS = ["VISp", "VISam"]
MIN_UNITS_PER_AREA = 20
QUALITY_FILTERS = {
    "isi_violations": 0.5,
    "amplitude_cutoff": 0.1,
    "presence_ratio": 0.95,
}


def parse_areas(value):
    if isinstance(value, (list, set)):
        return list(value)
    elif isinstance(value, str):
        cleaned = value.strip("[]{}").replace("'", "").replace('"', "")
        return [a.strip() for a in cleaned.split(",") if a.strip()]
    return []


def has_areas(value, areas):
    parsed = parse_areas(value)
    return all(a in parsed for a in areas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache_dir", type=str, required=True)
    args = parser.parse_args()

    cache = VisualBehaviorNeuropixelsProjectCache.from_s3_cache(
        cache_dir=args.cache_dir
    )

    print("Loading session and unit tables...")
    sessions = cache.get_ecephys_session_table()
    units = cache.get_unit_table()

    # ── 1. Show all session-level columns that might indicate novelty ──
    print(f"\nSession table columns ({len(sessions.columns)}):")
    novelty_candidates = [c for c in sessions.columns
                          if any(kw in c.lower() for kw in
                                 ["novel", "familiar", "experience", "image_set",
                                  "session_type", "prior", "exposure"])]
    print(f"  Novelty-related: {novelty_candidates}")

    # Show unique values for each candidate
    for col in novelty_candidates:
        vals = sessions[col].value_counts(dropna=False)
        print(f"\n  {col}:")
        for v, count in vals.items():
            print(f"    {v}: {count}")

    # ── 2. Filter to sessions with both VISp + VISam ──
    both_areas = sessions[
        sessions["structure_acronyms"].apply(lambda x: has_areas(x, AREAS))
    ]
    print(f"\nSessions with VISp + VISam: {len(both_areas)}")

    # ── 3. Show experience_level / session_type breakdown for these sessions ──
    for col in novelty_candidates:
        if col in both_areas.columns:
            print(f"\n  {col} for VISp+VISam sessions:")
            vals = both_areas[col].value_counts(dropna=False)
            for v, count in vals.items():
                print(f"    {v}: {count}")

    # ── 4. Find novel-image sessions with adequate unit counts ──
    # Try to identify which column marks novelty
    novel_col = None
    novel_values = []

    if "experience_level" in both_areas.columns:
        novel_col = "experience_level"
        # Typical values: "Familiar", "Novel 1", "Novel >1"
        all_vals = both_areas[novel_col].unique()
        novel_values = [v for v in all_vals if "novel" in str(v).lower()]
        print(f"\n  Novel experience levels: {novel_values}")
    elif "session_type" in both_areas.columns:
        novel_col = "session_type"
        all_vals = both_areas[novel_col].unique()
        novel_values = [v for v in all_vals if "novel" in str(v).lower()]

    if novel_col and novel_values:
        novel_sessions = both_areas[both_areas[novel_col].isin(novel_values)]
        print(f"\nNovel-image sessions with VISp+VISam: {len(novel_sessions)}")

        # Check unit counts
        good_units = units[
            (units["isi_violations"] < QUALITY_FILTERS["isi_violations"])
            & (units["amplitude_cutoff"] < QUALITY_FILTERS["amplitude_cutoff"])
            & (units["presence_ratio"] > QUALITY_FILTERS["presence_ratio"])
        ]

        viable_novel = []
        for sid in novel_sessions.index:
            row = novel_sessions.loc[sid]
            unit_counts = {}
            ok = True
            for area in AREAS:
                mask = (
                    (good_units["ecephys_session_id"] == sid)
                    & (good_units["structure_acronym"] == area)
                )
                n = int(mask.sum())
                unit_counts[area] = n
                if n < MIN_UNITS_PER_AREA:
                    ok = False

            genotype = str(row.get("genotype", "unknown"))
            if "Sst" in genotype or "SST" in genotype:
                geno_short = "SST"
            elif "Vip" in genotype or "VIP" in genotype:
                geno_short = "VIP"
            elif "Slc17a7" in genotype or genotype == "wt/wt":
                geno_short = "Slc17a7"
            else:
                geno_short = genotype[:20]

            mouse_id = int(row.get("mouse_id", -1)) if "mouse_id" in row.index else -1
            exp_level = str(row.get(novel_col, "?"))

            entry = {
                "session_id": sid,
                "experience_level": exp_level,
                "genotype": geno_short,
                "mouse_id": mouse_id,
                "VISp_units": unit_counts.get("VISp", 0),
                "VISam_units": unit_counts.get("VISam", 0),
                "viable": ok,
            }
            viable_novel.append(entry)

        df = pd.DataFrame(viable_novel)
        n_viable = df["viable"].sum()

        print(f"\n{'='*80}")
        print(f"NOVEL-IMAGE SESSIONS WITH VISp + VISam")
        print(f"{'='*80}")
        print(f"Total novel sessions with both areas: {len(df)}")
        print(f"Viable (≥{MIN_UNITS_PER_AREA} units in both): {n_viable}")

        if not df.empty:
            print(f"\n{'Session':>12s}  {'ExpLevel':>12s}  {'Geno':>8s}  "
                  f"{'Mouse':>8s}  {'VISp':>5s}  {'VISam':>5s}  {'OK':>4s}")
            print(f"{'-'*65}")
            for _, r in df.sort_values("viable", ascending=False).iterrows():
                ok_str = "YES" if r["viable"] else "no"
                print(f"{r['session_id']:>12d}  {r['experience_level']:>12s}  "
                      f"{r['genotype']:>8s}  {str(r['mouse_id']):>8s}  "
                      f"{r['VISp_units']:>5d}  {r['VISam_units']:>5d}  {ok_str:>4s}")

            if n_viable > 0:
                viable_df = df[df["viable"]]
                print(f"\nGenotype breakdown (viable): "
                      f"{viable_df['genotype'].value_counts().to_dict()}")
                print(f"Unique mice (viable): {viable_df['mouse_id'].nunique()}")
                print(f"Experience levels (viable): "
                      f"{viable_df['experience_level'].value_counts().to_dict()}")

        # ── 5. Also check: are any of our 10 existing sessions from mice
        #    that also have a novel session? (within-mouse comparison) ──
        existing_mice = {570299, 568963, 578003, 574078, 576323,
                         570301, 599294, 560962, 544836, 585329}
        if n_viable > 0:
            viable_df = df[df["viable"]]
            overlap_mice = existing_mice & set(viable_df["mouse_id"].values)
            if overlap_mice:
                print(f"\nMice with BOTH familiar (existing) and novel (available) sessions:")
                for mid in overlap_mice:
                    novel_sids = viable_df[viable_df["mouse_id"] == mid]["session_id"].tolist()
                    print(f"  Mouse {mid}: novel sessions = {novel_sids}")
                print("  → Within-mouse familiar vs. novel comparison possible!")
            else:
                print(f"\nNo overlap between existing mice and viable novel sessions.")
                print(f"  Familiar/novel comparison would be across-mouse (weaker but still valid).")

    else:
        print("\nCould not identify a novelty column. Showing all session table columns:")
        for col in sorted(sessions.columns):
            print(f"  {col}: {sessions[col].dtype} — {sessions[col].nunique()} unique")


if __name__ == "__main__":
    main()