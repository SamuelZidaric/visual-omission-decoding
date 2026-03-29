# Decoding Omission Responses Across the Mouse Visual Hierarchy

## Project Summary

A computational neuroscience project investigating **predictive processing** in the mouse visual cortex using the [Allen Brain Observatory Visual Behavior Neuropixels](https://allensdk.readthedocs.io/en/latest/visual_behavior_neuropixels.html) dataset.

**Core question:** Can a machine learning classifier decode pure negative prediction errors (omitted stimulus trials) from population spiking activity, and does decoding accuracy or latency differ between primary visual cortex (V1 / VISp) and higher-order anteromedial visual area (AM / VISam)?

## Background

Predictive processing theory proposes the brain actively predicts incoming sensory input and primarily processes "surprise" — prediction errors. When an expected visual stimulus is **omitted** (a blank screen instead of the predicted image), any neural activity represents a pure, internally-generated expectation signal, free from bottom-up sensory contamination.

Recent literature (2021–2026) shows:
- Omission responses **do occur in V1** — in both L2/3 and L4/5 (Price & Gavornik 2025; Keller et al. 2024)
- However, higher-order and subcortical regions may host more **"pure" omission encoders** (Chao et al. 2025, Science Advances)
- The field is actively debating whether V1 omission signals represent true prediction errors vs. stimulus-specific adaptation

This means the question is **not** "does omission coding exist in V1?" (answer: yes) but rather: **is the omission signal qualitatively different across the visual hierarchy?**

## Dataset Feasibility (Validated)

We queried the Allen Visual Behavior Neuropixels metadata on 2026-03-29:

| Metric | Value |
|---|---|
| Sessions with simultaneous VISp + VISam | **99** |
| Median high-quality units in VISam | **51** (IQR: 36–64) |
| Median high-quality units in VISp | **49** (IQR: 39–70) |
| Omission trials per session | **~200–250** (awaiting confirmation) |

Quality filter thresholds used: `isi_violations < 0.5`, `amplitude_cutoff < 0.1`, `presence_ratio > 0.95`.

**Conclusion:** Dataset fully supports the project. Sessions requiring ≥20 good units in both areas still leaves ~90+ viable sessions.

## Key Design Decisions

1. **Modality:** Spiking activity (firing rates) only. LFP spectral analysis deferred to v2.
2. **Class balance:** Omissions (~5% of trials) will be balanced via undersampling the "expected" class. Within-session analysis preferred over cross-session pooling.
3. **Success criterion:** Permutation testing (1,000 label shuffles). A result is significant if decoding accuracy falls outside the 99th percentile of the null distribution (p < 0.01). No arbitrary accuracy threshold.
4. **Classifier:** Logistic regression or linear SVM. Lightweight, interpretable, standard in the field.
5. **Cross-validation:** Stratified K-Fold or Leave-One-Out, depending on final trial counts.

## Tech Stack

- Python 3.9+
- `allensdk` — data access and metadata
- `numpy`, `pandas` — data manipulation
- `scikit-learn` — classification and permutation testing
- `matplotlib`, `seaborn` — visualization
- NWB (Neurodata Without Borders) file format

## Key References

1. Price & Gavornik (2025). *Learned response dynamics reflect stimulus timing and encode temporal expectation violations in superficial layers of mouse V1.* eLife. [DOI](https://elifesciences.org/reviewed-preprints/94727)
2. Keller, Mrsic-Flogel et al. (2024). *Cooperative thalamocortical circuit mechanism for sensory prediction errors.* Nature. [DOI](https://www.nature.com/articles/s41586-024-07851-w)
3. Chao et al. (2025). *Diversity of omission responses to visual images across brain-wide cortical and subcortical circuits.* Science Advances. [DOI](https://www.science.org/doi/10.1126/sciadv.adv5651)
4. Audette & Schneider (2025). Review citing V1 negative mismatch responses. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12212881/)

## Project Structure

```
neuro-omission-decoding/
├── README.md
├── ROADMAP.md
├── LITERATURE.md
├── DECISIONS.md
├── CLAUDE_PROJECT.md        # System prompt for Claude project/Claude Code
├── scripts/
│   ├── 01_check_feasibility.py
│   ├── 02_extract_spikes.py
│   ├── 03_build_features.py
│   ├── 04_decode.py
│   └── 05_visualize.py
├── notebooks/               # exploratory Jupyter notebooks
├── data/
│   └── allen_vbn_cache/     # metadata cache (gitignored)
├── results/
└── requirements.txt
```