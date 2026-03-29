"""
check_omission_per_image.py
Quick diagnostic: how many omission trials per image identity?
Determines feasibility of image-identity decoding from omission responses.

Usage:
    python check_omission_per_image.py --session_id 1064644573 --cache_dir .\allen_vbn_cache
"""

import argparse
import os
import pandas as pd
from allensdk.brain_observatory.behavior.behavior_project_cache.behavior_neuropixels_project_cache import (
    VisualBehaviorNeuropixelsProjectCache,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session_id", type=int, required=True)
    parser.add_argument("--cache_dir", type=str, required=True)
    args = parser.parse_args()

    cache = VisualBehaviorNeuropixelsProjectCache.from_s3_cache(cache_dir=args.cache_dir)
    print(f"Loading session {args.session_id}...")
    session = cache.get_ecephys_session(ecephys_session_id=args.session_id)
    stim = session.stimulus_presentations

    print(f"\nTotal stimulus presentations: {len(stim)}")
    print(f"Columns: {list(stim.columns)}")

    # Show what the omitted column looks like
    print(f"\n'omitted' dtype: {stim['omitted'].dtype}")
    print(f"'omitted' value counts:\n{stim['omitted'].value_counts()}")

    # Filter to task stimuli (same logic as 02_extract_spikes.py)
    non_task = {"gabor", "spontaneous", "flash", "natural_movie"}
    task_mask = ~stim["stimulus_name"].apply(
        lambda x: any(nt in str(x).lower() for nt in non_task)
    )
    task_stim = stim[task_mask].copy()
    print(f"\nTask stimuli: {len(task_stim)}")

    # What columns carry image identity?
    image_cols = [c for c in task_stim.columns if "image" in c.lower()]
    print(f"\nImage-related columns: {image_cols}")
    for col in image_cols:
        print(f"\n  {col} — unique values ({task_stim[col].nunique()}):")
        print(f"  {task_stim[col].unique()[:15]}")

    # Omission trials
    omissions = task_stim[task_stim["omitted"].astype(bool)]
    print(f"\n{'='*60}")
    print(f"Omission trials: {len(omissions)}")

    # Check image identity on omission trials
    # The key question: does the omission row still carry the image_name
    # of what WOULD have been shown?
    for col in image_cols:
        print(f"\nOmission '{col}' distribution:")
        counts = omissions[col].value_counts()
        print(counts.to_string())
        print(f"  Total: {counts.sum()}, Unique: {len(counts)}")

    # Also check: what's the expected (non-omission, non-change) distribution?
    if "is_change" in task_stim.columns:
        expected = task_stim[~task_stim["omitted"].astype(bool) & ~task_stim["is_change"].astype(bool)]
    else:
        expected = task_stim[~task_stim["omitted"].astype(bool)]

    print(f"\nExpected (non-change) trials: {len(expected)}")
    for col in image_cols[:2]:  # just first two to keep output manageable
        print(f"\nExpected '{col}' distribution:")
        counts = expected[col].value_counts()
        print(counts.to_string())

    # Summary for feasibility
    print(f"\n{'='*60}")
    print("FEASIBILITY SUMMARY")
    print(f"{'='*60}")
    if image_cols:
        col = image_cols[0]
        omit_counts = omissions[col].value_counts()
        min_per_image = omit_counts.min()
        n_images = len(omit_counts)
        print(f"Image identity column: '{col}'")
        print(f"Number of distinct images: {n_images}")
        print(f"Omissions per image: min={omit_counts.min()}, max={omit_counts.max()}, "
              f"mean={omit_counts.mean():.1f}")
        print(f"\nFor {n_images}-way image decoding from omission activity:")
        print(f"  ~{min_per_image} trials in smallest class")
        if min_per_image >= 20:
            print(f"  → FEASIBLE (≥20 trials per class)")
        elif min_per_image >= 10:
            print(f"  → MARGINAL (10-20 trials per class, consider LOO-CV)")
        else:
            print(f"  → NOT FEASIBLE for image-identity decoding")
            print(f"  → Fall back to binary omission-vs-expected decoding")


if __name__ == "__main__":
    main()