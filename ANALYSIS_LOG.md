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
| R007 | 2026-03-29 | 03_decode.py | 1064644573 | Late-window decoding 200–400ms, 100 perms | H3 REJECTED — VISp 97.4% > VISam 80.3% |
| R008 | 2026-03-29 | 03_decode.py | 1064644573 | Time-resolved decoding 0–500ms | VISp > VISam all bins, OFF-response at 275ms |
| R009 | 2026-03-29 | 03_decode.py | 1064644573 | Clean late-window 400–750ms, 100 perms | VISp 90.0% > VISam 75.1% — signal persists past OFF |
| R010 | 2026-03-29 | 02_extract_spikes.py | 1064644573 | Extraction 400–750ms | COMPLETE |
| R011 | 2026-03-29 | 02+03_decode.py | 1064644573 | **BASELINE CONTROL** −250–0ms | PASS — both at chance (47.6%, 51.2%) |
| R012 | 2026-03-29 | 03_decode.py | 1064644573 | Extended time-resolved 0–750ms, 15 bins | VISp 66%, VISam 62% at 725ms — converging |

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

### R011: Pre-stimulus baseline control (critical validation)
- **Date:** 2026-03-29
- **Script:** `02_extract_spikes.py` + `03_decode.py`
- **Session:** 1064644573
- **Purpose:** Rule out pre-existing brain state differences between omission and expected trials. If the decoder can distinguish the two conditions *before* the stimulus, the late-window results are confounded.
- **Parameters:**
  - Window: **−250 to 0 ms** (pre-stimulus baseline)
  - Bin width: 250 ms (single bin)
  - Decoder: same as R007/R009 (LogisticRegressionCV, 10 repeats, 5-fold CV)
  - Permutations: 100
- **Key results:**
  - **VISp: 0.476 ±0.023 (p=0.8416) — NOT SIGNIFICANT**
  - **VISam: 0.512 ±0.029 (p=0.2376) — NOT SIGNIFICANT**
  - Both areas decode at chance in the pre-stimulus window
- **Output files:**
  - `results/decoding/session_1064644573/w-250-0ms_b250ms/`
- **Interpretation:** **CRITICAL VALIDATION PASSED.** The brain state before the stimulus is indistinguishable between omission and expected trials. This confirms that:
  - The 90% VISp / 75% VISam decoding at 400–750ms is genuinely stimulus-locked
  - There is no slow behavioral drift or arousal confound driving the classification
  - All post-stimulus decoding results (R007, R008, R009) are validated
- **Impact:** Strengthens all prior findings. The persistent signal in the 400–750ms inter-stimulus interval is evoked by the trial events, not pre-existing.

---

### R012: Extended time-resolved decoding — 0–750ms (full ISI)
- **Date:** 2026-03-29
- **Script:** `03_decode.py --mode time_resolved --tr_tag w0-750ms_b50ms`
- **Session:** 1064644573
- **Parameters:**
  - 15 bins × 50ms, decoded independently
  - No permutation test
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
  | 525ms | 0.817 | 0.627 |
  | 575ms | 0.755 | 0.615 |
  | 625ms | 0.731 | 0.631 |
  | 675ms | 0.708 | 0.641 |
  | 725ms | 0.662 | 0.622 |

- **Key observations:**
  - VISp decays from 97.5% to 66.2% — never reaches chance
  - VISam decays from 96.0% to 62.2% — plateaus at ~63% from 475ms onward
  - The gap narrows: 20-point spread at 475ms → 4-point spread at 725ms
  - **Convergence:** Both areas approach ~63–66% by end of ISI, suggesting similar weak residual signal
  - Neither area reaches chance (50%) by 725ms — persistent trace throughout ISI
- **Output files:**
  - `results/decoding/session_1064644573/w0-750ms_b50ms/time_resolved_results.json`
  - `results/decoding/session_1064644573/w0-750ms_b50ms/time_resolved_accuracy.png`

---

## Pending runs

| Run ID | Script | Session(s) | Parameters | Purpose |
|--------|--------|------------|------------|---------|
| R013 | 03_decode.py | 1064644573 | w400-750ms, 1000 permutations | Full permutation test on clean window |
| R014 | 02+03 | 5 pilot sessions | w400-750ms, 100 permutations | Multi-session validation of VISp > VISam finding |
| R015 | 03_decode.py | 1064644573 | trial-history matched analysis | Control for trial history effects |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-29 | Log created. R001–R004 recorded. Schema v1.0. |
| 2026-03-29 | R005–R006 recorded. Pending runs renumbered. Output paths now include window config. |
| 2026-03-29 | R007–R010 recorded. First decoding results: H3 rejected on pilot session (VISp > VISam). OFF-response confound identified. 400–750ms window tested. |
| 2026-03-29 | R011–R012 recorded. Baseline control PASSED (chance-level pre-stimulus). Extended time-resolved shows convergence at 725ms. |