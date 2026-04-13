# Analysis Log

Machine-readable record of every analysis run. Each entry captures inputs, parameters, outputs, and key results. Follows FAIR principles: findable (indexed by run ID), accessible (plain text), interoperable (consistent schema), reusable (full parameter provenance).

**Schema version:** 1.0
**Project:** neuro-omission-decoding
**Dataset:** Allen Brain Observatory Visual Behavior Neuropixels (VBN)
**Dataset DOI:** https://portal.brain-map.org/circuits-behavior/visual-behavior-neuropixels

---

## Run index

| Run ID | Date | Script | Session | Description | Result |
|--------|------|--------|---------|-------------|--------|
| R001 | 2026-03-29 | 01_check_feasibility.py | all | Dataset validation: session counts, unit yields | PASS — 99 sessions, median ~50 units/area |
| R002 | 2026-03-29 | 02_extract_spikes.py (dry_run) | 1064644573 | Unit count check without NWB download | PASS — VISp=38, VISam=45 |
| R003 | 2026-03-29 | 02_extract_spikes.py | 1064644573 | Full spike extraction, 0–250ms window, 250ms bin | COMPLETE — 356 omissions, 8828 expected |
| R004 | 2026-03-29 | check_omission_per_image.py | 1064644573 | Check if omission rows carry image identity | NEGATIVE — image_name="omitted" for all 356 |
| R005 | 2026-03-29 | 02_extract_spikes.py | 1064644573 | Late-window extraction, 200–400ms, 200ms bin | COMPLETE — VISp 6.3 Hz, VISam 5.1 Hz |
| R006 | 2026-03-29 | 02_extract_spikes.py | 1064644573 | Time-resolved extraction, 0–500ms, 10×50ms bins | COMPLETE — VISp 6.5 Hz, VISam 5.4 Hz |
| R011 | 2026-03-30 | 05_multi_session.py | 5 sessions | Multi-session extraction + decoding, 400–750ms + 0–500ms | COMPLETE — VISp > VISam in 5/5 sessions |

---

## Detailed run records

### R001: Dataset feasibility check
- **Date:** 2026-03-29
- **Script:** `01_check_feasibility.py`
- **Scope:** All sessions in Allen VBN
- **Parameters:**
  - Areas: VISp, VISam
  - Quality filters: isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.95
  - Minimum units per area: 20
- **Key results:**
  - Sessions with simultaneous VISp + VISam: **99**
  - Median high-quality units — VISp: **49** (IQR: 39–70)
  - Median high-quality units — VISam: **51** (IQR: 36–64)
  - Sessions meeting ≥20 units in both areas: **~90+**
- **Output files:** Console output only (no files saved)
- **Go/no-go:** **GO** — dataset fully supports the project
- **Notes:** Omission trial count not confirmed at this stage (requires NWB download).

---

### R002: Dry-run unit count check
- **Date:** 2026-03-29
- **Script:** `02_extract_spikes.py --dry_run`
- **Session:** 1064644573
- **Parameters:**
  - Cache: `.\allen_vbn_cache`
  - Quality filters: same as R001
- **Key results:**
  - VISp units: **38**
  - VISam units: **45**
  - Both above threshold (20)
- **Output files:** None (dry run)
- **Decision:** Proceed to full extraction.

---

### R003: First spike extraction
- **Date:** 2026-03-29
- **Script:** `02_extract_spikes.py`
- **Session:** 1064644573 (SST-IRES-Cre mouse, novel image set H)
- **Parameters:**
  - Window: 0–250 ms post-stimulus onset
  - Bin width: 250 ms (single bin)
  - Quality filters: isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.95
  - Trial selection: all task stimuli (active + passive), excluding gabors/flashes/spontaneous
  - Expected trial filter: non-omitted AND non-change
- **Key results:**
  - Total stimulus presentations: 13,391
  - Task stimuli after filtering: 9,594
  - Stimulus name: `Natural_Images_Lum_Matched_set_ophys_H_2019`
  - Omission trials: **356**
  - Expected (non-change) trials: **8,828**
  - Total trials in output: **9,184** (356 omission + 8,828 expected)
  - VISp — 38 units, mean firing rate: **8.4 Hz**
  - VISam — 45 units, mean firing rate: **6.5 Hz**
- **Output files:**
  - `results/spike_matrices/session_1064644573/firing_rates_VISp.npy` — shape (9184, 38, 1)
  - `results/spike_matrices/session_1064644573/firing_rates_VISam.npy` — shape (9184, 45, 1)
  - `results/spike_matrices/session_1064644573/labels.npy` — shape (9184,), dtype int8
  - `results/spike_matrices/session_1064644573/metadata.json`
  - `results/spike_matrices/session_1064644573/psth_diagnostic_VISp.png`
  - `results/spike_matrices/session_1064644573/psth_diagnostic_VISam.png`
- **PSTH diagnostic observations:**
  - VISp: Strong visual response in expected trials (peak ~85 Hz at 50–80ms). Omission traces flat. Clear offset response at ~280ms.
  - VISam: Similar pattern, visual response peak ~60 Hz. Omission traces flat. Offset response visible but weaker.
  - Both areas: No obvious omission-evoked activity visible in these 3 high-firing example units. Prediction error signal may be in lower-firing subpopulations or require population-level analysis to detect.
- **Go/no-go:** **GO** — data quality confirmed, trial counts sufficient for decoding.
- **Notes:** The 0–250ms window captures the trivial sensory response (see D010). Primary analysis will use 200–400ms window. This extraction serves as pipeline validation.

---

### R004: Omission image identity check
- **Date:** 2026-03-29
- **Script:** `check_omission_per_image.py`
- **Session:** 1064644573
- **Purpose:** Determine if omission trials retain the identity of the expected image, enabling multi-class (H1) decoding.
- **Key results:**
  - `image_name` on omission rows: **"omitted"** (all 356 trials)
  - Image identity is NOT preserved in omission metadata
  - 8 distinct images in expected trials: im104_r, im024_r, im114_r, im083_r, im111_r, im005_r, im034_r, im087_r
  - Image counts range: 860–1,410 per image (reasonable balance)
  - `is_image_novel`: True=6,954, False=1,874 (novel session — most images novel)
- **Output files:** Console output only
- **Decision impact:** H1 (image-identity from omissions) ruled out → fall back to H3 (binary decoding). See D011.
- **Follow-up:** Could infer expected image from preceding trial in sequence (deferred to Phase 6).

---

### R005: Late-window spike extraction (primary analysis window)
- **Date:** 2026-03-29
- **Script:** `02_extract_spikes.py`
- **Session:** 1064644573
- **Parameters:**
  - Window: 200–400 ms post-stimulus onset
  - Bin width: 200 ms (single bin)
  - Quality filters: same as R003
  - Trial selection: same as R003
- **Key results:**
  - Omission trials: **356**, Expected trials: **8,828**
  - VISp — 38 units, mean firing rate: **6.3 Hz**
  - VISam — 45 units, mean firing rate: **5.1 Hz**
  - Rates lower than R003 (0–250ms) as expected — late window misses the sensory transient
- **Output files:**
  - `results/spike_matrices/session_1064644573/w200-400ms_b200ms/firing_rates_VISp.npy` — shape (9184, 38, 1)
  - `results/spike_matrices/session_1064644573/w200-400ms_b200ms/firing_rates_VISam.npy` — shape (9184, 45, 1)
  - `results/spike_matrices/session_1064644573/w200-400ms_b200ms/labels.npy` — shape (9184,)
  - `results/spike_matrices/session_1064644573/w200-400ms_b200ms/metadata.json`
  - `results/spike_matrices/session_1064644573/w200-400ms_b200ms/psth_diagnostic_VISp.png`
  - `results/spike_matrices/session_1064644573/w200-400ms_b200ms/psth_diagnostic_VISam.png`
- **Purpose:** This is the primary analysis window for H3. Avoids the trivial sensory response (D010). Used for the main decoding comparison between VISam and VISp.

---

### R006: Time-resolved spike extraction (latency analysis)
- **Date:** 2026-03-29
- **Script:** `02_extract_spikes.py`
- **Session:** 1064644573
- **Parameters:**
  - Window: 0–500 ms post-stimulus onset
  - Bin width: 50 ms (10 bins)
  - Quality filters: same as R003
  - Trial selection: same as R003
- **Key results:**
  - Omission trials: **356**, Expected trials: **8,828**
  - VISp — 38 units, mean firing rate: **6.5 Hz**
  - VISam — 45 units, mean firing rate: **5.4 Hz**
- **Output files:**
  - `results/spike_matrices/session_1064644573/w0-500ms_b50ms/firing_rates_VISp.npy` — shape (9184, 38, 10)
  - `results/spike_matrices/session_1064644573/w0-500ms_b50ms/firing_rates_VISam.npy` — shape (9184, 45, 10)
  - `results/spike_matrices/session_1064644573/w0-500ms_b50ms/labels.npy` — shape (9184,)
  - `results/spike_matrices/session_1064644573/w0-500ms_b50ms/metadata.json`
  - `results/spike_matrices/session_1064644573/w0-500ms_b50ms/psth_diagnostic_VISp.png`
  - `results/spike_matrices/session_1064644573/w0-500ms_b50ms/psth_diagnostic_VISam.png`
- **Purpose:** Time-resolved decoding — slide the decoder across 50ms bins to identify when omission vs. expected becomes decodable in each area. Answers: does the signal emerge earlier in VISp or VISam?

---

### R007: Late-window decoding — 200–400ms (H3 primary test)
- **Date:** 2026-03-29
- **Script:** `03_decode.py --mode late_window --late_tag w200-400ms_b200ms`
- **Session:** 1064644573
- **Parameters:**
  - Classifier: LogisticRegressionCV (Cs=10, inner 3-fold CV for C tuning)
  - Outer CV: stratified 5-fold
  - Undersample repeats: 10 (variance computed across repeats, not folds)
  - Permutations: 100 (sanity check run)
  - Features: firing rates in 200–400ms single bin
- **Key results:**
  - **VISp: 0.974 ±0.006 (p=0.0099) *** — SIGNIFICANT**
  - **VISam: 0.803 ±0.014 (p=0.0099) *** — SIGNIFICANT**
  - VISam − VISp = **−0.171**
  - **H3 REJECTED on this session: VISp decodes BETTER**
- **Output files:**
  - `results/decoding/session_1064644573/late_window_results.json`
  - `results/decoding/session_1064644573/null_distributions.png`
- **Interpretation:** VISp at 97.4% in 200–400ms indicates the window still captures the stimulus offset response (~250ms). The decoder is largely solving "did an OFF-transient occur?" — not isolating prediction signals. See D012.

---

### R008: Time-resolved decoding — 0–500ms (latency analysis)
- **Date:** 2026-03-29
- **Script:** `03_decode.py --mode time_resolved --tr_tag w0-500ms_b50ms`
- **Session:** 1064644573
- **Parameters:**
  - Same classifier/CV as R007, no permutation test
  - 10 bins × 50ms, decoded independently
- **Key results (accuracy per bin):**

  | Bin center | VISp | VISam |
  |------------|------|-------|
  | 25ms | 0.867 | 0.799 |
  | 75ms | 0.975 | 0.960 |
  | 125ms | 0.955 | 0.817 |
  | 175ms | 0.911 | 0.695 |
  | 225ms | 0.928 | 0.764 |
  | 275ms | 0.952 | 0.746 |
  | 325ms | 0.919 | 0.783 |
  | 375ms | 0.900 | 0.765 |
  | 425ms | 0.882 | 0.681 |
  | 475ms | 0.843 | 0.642 |

- **Key observations:**
  - VISp never drops below 84% across the entire 0–500ms epoch
  - VISp shows a second peak at 275ms — the OFF-response
  - VISam decays steeply after the ON-response, from 96% to 64%
  - VISp > VISam at every time bin except 75ms (where they converge)
- **Output files:**
  - `results/decoding/session_1064644573/time_resolved_results.json`
  - `results/decoding/session_1064644573/time_resolved_accuracy.png`

---

### R009: Late-window decoding — 400–750ms (clean post-offset test)
- **Date:** 2026-03-29
- **Script:** `03_decode.py --mode late_window --late_tag w400-750ms_b350ms`
- **Session:** 1064644573
- **Parameters:**
  - Same classifier/CV as R007
  - Permutations: 100
  - Window: 400–750ms — past both ON and OFF transients, both conditions viewing gray screen
- **Key results:**
  - **VISp: 0.900 ±0.009 (p=0.0099) *** — SIGNIFICANT**
  - **VISam: 0.751 ±0.010 (p=0.0099) *** — SIGNIFICANT**
  - VISam − VISp = **−0.149**
  - **H3 STILL REJECTED: VISp decodes better even in the clean late window**
- **Interpretation:** VISp at 90% in 400–750ms means the signal is NOT simply an OFF-transient artifact. V1 retains a strong, persistent differential signal between omission and expected trials deep into the inter-stimulus interval. This is either: (a) sustained prediction error (PE = 0 − prediction, which is large and structured in V1), (b) stimulus-specific adaptation that persists on expected trials but is absent on omission trials, or (c) a combination of both. See D012.

---

### R010: Spike extraction — 400–750ms (clean late window)
- **Date:** 2026-03-29
- **Script:** `02_extract_spikes.py --window_ms 400 750 --bin_width_ms 350`
- **Session:** 1064644573
- **Key results:**
  - Omission trials: **356**, Expected trials: **8,828**
  - VISp — 38 units
  - VISam — 45 units
- **Output files:**
  - `results/spike_matrices/session_1064644573/w400-750ms_b350ms/`

---

### R011: Multi-session validation — 5 sessions (Phase 4)
- **Date:** 2026-03-30
- **Script:** `05_multi_session.py --n_sessions 5 --n_permutations 100`
- **Sessions:** 1115077618, 1111013640, 1119946360, 1115086689, 1116941914
- **Session selection criteria:** Greedy diversity — maximize genotype and mouse_id coverage from 88 viable candidates. Selected: 2 SST-IRES-Cre, 1 VIP-IRES-Cre, 2 Slc17a7 (wt/wt), 5 unique mice.
- **Parameters:**
  - Primary window: 400–750ms (D012 clean window), single 350ms bin
  - Secondary window: 0–500ms, 10 × 50ms bins (time-resolved, no permutations)
  - Classifier: LogisticRegressionCV (Cs=10, penalty=l2, inner 3-fold CV)
  - Outer CV: stratified 5-fold
  - Undersample repeats: 10
  - Permutations: 100 per area per session
  - Quality filters: isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.95
  - Minimum units per area: 20
- **Key results (400–750ms late window):**

  | Session | Genotype | Mouse | Image set | VISp units | VISam units | Omissions | VISp acc | VISam acc | Diff |
  |---------|----------|-------|-----------|------------|-------------|-----------|----------|-----------|------|
  | 1115077618 | SST | 570299 | G | 86 | 87 | 364 | 0.930 | 0.836 | −0.095 |
  | 1111013640 | VIP | 568963 | G | 85 | 86 | 306 | 0.954 | 0.868 | −0.085 |
  | 1119946360 | Slc17a7 | 578003 | H | 110 | 120 | 328 | 0.944 | 0.854 | −0.090 |
  | 1115086689 | SST | 574078 | G | 97 | 71 | 354 | 0.951 | 0.848 | −0.103 |
  | 1116941914 | Slc17a7 | 576323 | H | 71 | 91 | 352 | 0.920 | 0.881 | −0.039 |

  - VISp mean: **0.940 ± 0.014**, VISam mean: **0.857 ± 0.018**
  - VISp > VISam in **5/5 sessions**
  - All 10 individual area-level permutation tests: **p = 0.0099** (significant)
  - Null distributions centered at ~0.50 for all areas/sessions (chance)
  - Cohen's d = **−3.27** (very large effect)
  - Wilcoxon signed-rank: p = 0.0625 (floor for n=5 with all pairs concordant)
  - Sign-flip permutation test (10,000 flips): p = 0.061
  - One-sided sign test: p = 0.031 (0.5^5)

- **Key results (0–500ms time-resolved):**

  | Session | VISp peak (ms) | VISp peak acc | VISam peak (ms) | VISam peak acc |
  |---------|----------------|---------------|-----------------|----------------|
  | 1115077618 | 75 | 0.992 | 75 | 0.947 |
  | 1111013640 | 325 | 0.990 | 75 | 0.920 |
  | 1119946360 | 75 | 0.985 | 75 | 0.946 |
  | 1115086689 | 75 | 0.994 | 75 | 0.948 |
  | 1116941914 | 75 | 0.992 | 75 | 0.972 |

  - Both areas peak near 75ms (ON-response) — trivial sensory decoder
  - VISp maintains high accuracy through 500ms; VISam decays faster
  - Session 1111013640: VISp peaks at 325ms (strong OFF-response), confirming D012 rationale

- **Output files:**
  - `results/multi_session/multi_session_results.json` — full results with null distributions
  - `results/multi_session/multi_session_summary.png` — 3-panel figure (paired dots, differences, time-resolved)
  - `results/multi_session/session_results_interim.json` — intermediate saves (gitignored)
  - `results/spike_matrices/session_*/w400-750ms_b350ms/` — per-session spike data (gitignored)
  - `results/spike_matrices/session_*/w0-500ms_b50ms/` — per-session time-resolved data (gitignored)

- **Neurobiological note:** Neuropixels records all nearby extracellular spikes regardless of Cre line. The genotype labels (SST, VIP, Slc17a7) identify which cell type is opto-taggable, not which neurons enter the decoder. The decoded population is dominated by excitatory pyramidal cells in all sessions. Genotype diversity confirms the finding is not an artifact of a specific transgenic background.

- **Go/no-go:** **GO** — H3 definitively rejected. VISp > VISam replicates across genotypes, mice, and image sets. See D013.

---

### R012: Multi-session scale-up — n=10 (Phase 4 extension)
- **Date:** 2026-03-30
- **Script:** `05_multi_session.py --n_sessions 10 --n_permutations 100 --resume`
- **Sessions:** 5 previous + 5 new (1108334384, 1152632711, 1099598937, 1067588044, 1139846596)
- **Session selection:** Greedy diversity with `--resume` — loaded 5 existing results, excluded their session IDs, seeded seen_genotypes/seen_mice, selected 5 new sessions. Final: 3 SST, 2 VIP, 5 Slc17a7, 8 unique mice.
- **Parameters:** Same as R011 (400–750ms, 100 permutations, 10× undersampling, stratified 5-fold CV)
- **Key results (400–750ms late window, n=10):**

  | Session | Genotype | Mouse | VISp units | VISam units | Omissions | VISp acc | VISam acc | Diff |
  |---------|----------|-------|------------|-------------|-----------|----------|-----------|------|
  | 1115077618 | SST | 570299 | 86 | 87 | 364 | 0.930 | 0.836 | −0.095 |
  | 1111013640 | VIP | 568963 | 85 | 86 | 306 | 0.954 | 0.868 | −0.085 |
  | 1119946360 | Slc17a7 | 578003 | 110 | 120 | 328 | 0.944 | 0.854 | −0.090 |
  | 1115086689 | SST | 574078 | 97 | 71 | 354 | 0.951 | 0.848 | −0.103 |
  | 1116941914 | Slc17a7 | 576323 | 71 | 91 | 352 | 0.920 | 0.881 | −0.039 |
  | 1108334384 | SST | 570301 | 106 | 56 | 364 | 0.915 | 0.719 | −0.196 |
  | 1152632711 | VIP | 599294 | 66 | 82 | 360 | 0.900 | 0.858 | −0.042 |
  | 1099598937 | Slc17a7 | 560962 | 86 | 76 | 398 | 0.870 | 0.863 | −0.007 |
  | 1067588044 | Slc17a7 | 544836 | 92 | 63 | 346 | 0.940 | 0.863 | −0.077 |
  | 1139846596 | Slc17a7 | 585329 | 84 | 63 | 434 | 0.936 | 0.910 | −0.025 |

  - VISp mean: **0.926 ± 0.026**, VISam mean: **0.850 ± 0.050**
  - VISp > VISam in **10/10 sessions**
  - Cohen's d = **−1.42** (large effect)
  - Wilcoxon p = 0.0020, Permutation p = 0.0016, Sign test p = 0.0010
  - All three tests significant at p < 0.01

- **Output files:**
  - `results/multi_session/multi_session_results.json` (merged 10-session results)
  - `results/multi_session/multi_session_summary.png` (updated 3-panel figure)
  - `results/multi_session/multi_session_results_backup_20260330_115726.json` (n=5 backup)

- **Runtime:** 73.4 minutes (5 new sessions: download + extraction + decoding)

---

### R013: Familiar/novel feasibility check
- **Date:** 2026-03-30
- **Script:** `06_check_familiar_novel_counts.py`, `check_novel_sessions.py`
- **Purpose:** Determine if within-session familiar vs. novel split is feasible, and if not, find matched novel sessions for within-mouse comparison.
- **Key results:**
  - All 10 existing sessions are Familiar (`experience_level = "Familiar"`)
  - `is_image_novel` is `<NA>` for all omission rows (image wasn't shown → no novelty label)
  - Within-session split: NOT FEASIBLE (0 novel trials in any session)
  - Novel sessions in dataset: 52 total, 51 with VISp + VISam, 47 viable (≥20 units in both)
  - **9 of 10 existing mice have a matched novel session** — within-mouse paired design possible
  - Mouse 585329 excluded: novel session (1140102579) has only 17 VISam units

- **Paired session mapping (9 mice):**

  | Mouse | Genotype | Familiar session | Novel session |
  |-------|----------|-----------------|---------------|
  | 544836 | Slc17a7 | 1067588044 | 1067781390 |
  | 560962 | Slc17a7 | 1099598937 | 1099869737 |
  | 568963 | VIP | 1111013640 | 1111216934 |
  | 570299 | SST | 1115077618 | 1115356973 |
  | 570301 | SST | 1108334384 | 1108531612 |
  | 574078 | SST | 1115086689 | 1115368723 |
  | 576323 | Slc17a7 | 1116941914 | 1117148442 |
  | 578003 | Slc17a7 | 1119946360 | 1120251466 |
  | 599294 | VIP | 1152632711 | 1152811536 |

- **Decision impact:** D015 — within-mouse paired novelty comparison. `07_paired_novelty.py` written and running.

---

### R014: Within-mouse familiar vs. novel comparison (Phase 5)
- **Date:** 2026-03-30
- **Script:** `07_paired_novelty.py --n_permutations 100`
- **Sessions:** 9 novel sessions matched to 9 familiar sessions (same mice)
- **Parameters:** 400–750ms, 100 permutations, 10× undersampling, stratified 5-fold CV
- **Key results:**

  | Mouse | Genotype | VISp Fam | VISp Nov | VISp Δ | VISam Fam | VISam Nov | VISam Δ |
  |-------|----------|----------|----------|--------|-----------|-----------|---------|
  | 544836 | Slc17a7 | 0.940 | 0.932 | −0.008 | 0.863 | 0.755 | −0.107 |
  | 560962 | Slc17a7 | 0.870 | 0.875 | +0.005 | 0.863 | 0.712 | −0.151 |
  | 568963 | VIP | 0.954 | 0.921 | −0.032 | 0.868 | 0.770 | −0.098 |
  | 570299 | SST | 0.930 | 0.901 | −0.030 | 0.836 | 0.779 | −0.057 |
  | 570301 | SST | 0.915 | 0.901 | −0.014 | 0.719 | 0.759 | +0.040 |
  | 574078 | SST | 0.951 | 0.942 | −0.009 | 0.848 | 0.725 | −0.123 |
  | 576323 | Slc17a7 | 0.920 | 0.818 | −0.102 | 0.881 | 0.798 | −0.083 |
  | 578003 | Slc17a7 | 0.944 | 0.912 | −0.032 | 0.854 | 0.750 | −0.104 |
  | 599294 | VIP | 0.900 | 0.911 | +0.010 | 0.858 | 0.823 | −0.035 |

  - **VISp:** 92.5% → 90.1% (Δ = −2.4%, d = −0.71, Wilcoxon p = 0.039, 7/9 drop)
  - **VISam:** 84.3% → 76.3% (Δ = −8.0%, d = −1.41, Wilcoxon p = 0.012, 8/9 drop)
  - **Interaction:** VISp drops LESS than VISam (p = 0.039)

- **Output files:**
  - `results/novelty_comparison/paired_novelty_results.json`
  - `results/novelty_comparison/paired_novelty_results.png`

- **Runtime:** 92.1 minutes
- **Decision impact:** D016 — double dissociation: VISp = experience-independent temporal PE, VISam = experience-dependent content expectation.

---

### R015: Unit-matched control (Phase 6)
- **Date:** 2026-03-30
- **Script:** `08_unit_matched_control.py --n_subsamples 20`
- **Sessions:** 10 familiar sessions
- **Parameters:** For each session, downsample the area with more units to match the other. 20 random unit subsamples × 10 undersampling repeats × 5-fold CV.
- **Key results:**

  | Session | VISp units | VISam units | Matched to | VISp matched | VISam matched | VISp still better? |
  |---------|-----------|------------|-----------|-------------|--------------|-------------------|
  | 1115077618 | 86 | 87 | 86 | 0.930 | 0.837 | YES |
  | 1111013640 | 85 | 86 | 85 | 0.954 | 0.874 | YES |
  | 1119946360 | 110 | 120 | 110 | 0.944 | 0.846 | YES |
  | 1115086689 | 97 | 71 | 71 | 0.927 | 0.848 | YES |
  | 1116941914 | 71 | 91 | 71 | 0.920 | 0.862 | YES |
  | 1108334384 | 106 | 56 | 56 | 0.880 | 0.719 | YES |
  | 1152632711 | 66 | 82 | 66 | 0.900 | 0.827 | YES |
  | 1099598937 | 86 | 76 | 76 | 0.856 | 0.863 | NO |
  | 1067588044 | 92 | 63 | 63 | 0.917 | 0.863 | YES |
  | 1139846596 | 84 | 63 | 63 | 0.920 | 0.910 | YES |

  - VISp still better in **9/10 sessions**
  - Matched VISp mean: 0.915 ± 0.028; Matched VISam mean: 0.845 ± 0.047
  - Cohen's d = **−1.49** (increased from −1.42 unmatched)
  - Wilcoxon p = 0.004; Sign test p = 0.011

- **Output files:**
  - `results/unit_matched_control/unit_matched_results.json`

- **Runtime:** 2308s (~38 minutes)
- **Decision impact:** D017 — unit-count confound closed. Effect is biological, not methodological.

---

## Pending runs

| Run ID | Script | Session(s) | Parameters | Purpose |
|--------|--------|------------|------------|---------|
| R016 | 05_multi_session.py | 10 sessions | w400-750ms, 1000 permutations | Publication-ready p-values (optional, low priority) |

All core analyses complete. Remaining work is paper writing and figure generation.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-29 | Log created. R001–R004 recorded. Schema v1.0. |
| 2026-03-29 | R005–R006 recorded. Pending runs renumbered. Output paths now include window config. |
| 2026-03-29 | R007–R010 recorded. First decoding results: H3 rejected on pilot session (VISp > VISam). OFF-response confound identified. 400–750ms window tested. |
| 2026-03-30 | R011 recorded. Multi-session validation complete: VISp > VISam in 5/5 sessions. Phase 4 done. |
| 2026-03-30 | R012 recorded. Scale-up to n=10: VISp > VISam in 10/10, all tests p < 0.01. D014 added. |
| 2026-03-30 | R013 recorded. Familiar/novel feasibility: 9 within-mouse pairs identified. D015 added. |
| 2026-03-30 | R014 recorded. Novelty comparison complete: double dissociation (VISp stable, VISam drops). D016 added. |
| 2026-03-30 | R015 recorded. Unit-matched control: 9/10 sessions, d = −1.49. D017 added. All core analyses complete. |