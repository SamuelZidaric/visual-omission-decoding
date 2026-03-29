# Roadmap

## Phase 0: Dataset Validation ✅
**Status: COMPLETE (2026-03-29)**

- [x] Query Allen VBN metadata for session/unit counts
- [x] Confirm simultaneous VISp + VISam coverage (99 sessions)
- [x] Confirm high-quality unit yields (median ~50 per area)
- [x] Confirm omission trial count from downloaded session (356 — exceeds 150 threshold)

**Go/no-go:** PASSED. 356 omissions per session, well above the 150 minimum.

---

## Phase 1: Literature & Hypothesis Lock-in ✅
**Status: COMPLETE (2026-03-29)**

- [x] Run Perplexity search for core papers (9 papers collected)
- [x] Identify that omission responses exist in V1 (reframes hypothesis)
- [ ] Read Chao et al. 2025 and Price & Gavornik 2025 in full (deferred — hypothesis locked without)
- [x] Finalize biological hypothesis → **H3 (binary omission-vs-expected, VISam vs. VISp)**
- [x] Reframe using predictive coding theory: VISam = prediction, VISp = prediction error (D009)
- [x] Check image-identity feasibility → NOT feasible, omission rows lack image_name (D011)
- [ ] Search for papers reporting actual decoding accuracies on omission trials (benchmark)

**Deliverable:** Locked hypothesis in DECISIONS.md (D009, D010, D011).

**Locked hypothesis (H3):** Binary omission-vs-expected decoding from late-window activity (200–400ms) is higher in VISam than VISp, reflecting a cleaner internally-generated prediction signal in the higher-order area.

---

## Phase 2: Data Pipeline ✅ (pilot session)
**Status: PILOT COMPLETE (2026-03-29)**

- [x] Download 1 pilot session — 1064644573, SST-IRES-Cre, novel image set H (~3 GB)
- [x] Extract spike times per unit, aligned to stimulus onset
- [x] Build trial matrix: units × time bins × trials
- [x] Separate omission (356) vs. expected (8,828) trials, excluding change trials
- [x] Bin spikes — two configurations:
  - [x] Late window: 200–400ms, single 200ms bin → `w200-400ms_b200ms/`
  - [x] Time-resolved: 0–500ms, 10 × 50ms bins → `w0-500ms_b50ms/`
- [x] Verify data integrity: diagnostic PSTHs confirm strong visual response in expected, flat in omission
- [x] Fix output directory structure to include window parameters (no overwrites)
- [ ] Download 4 more pilot sessions (~14 GB additional)

**Go/no-go:** PASSED. Data quality confirmed. PSTHs show clear sensory response in expected trials, baseline in omissions. Late-window rates (VISp: 6.3 Hz, VISam: 5.1 Hz) are lower than early-window — expected, as we're past the sensory transient.

**Deliverable:** `02_extract_spikes.py` producing clean numpy arrays. ✅

---

## Phase 3: Feature Engineering & Decoding ✅ (pilot session)
**Status: PILOT COMPLETE (2026-03-29)**

- [x] Construct population firing rate vectors per trial (flatten units × bins)
- [x] Undersample expected trials to match omission count (356 each → 712 total)
- [x] Train LogisticRegressionCV — within-session, balanced classes, stratified 5-fold CV, auto C tuning
- [x] Run permutation test (100 shuffles sanity check) → null distribution per area
- [x] Compare decoding accuracy: VISp vs. VISam
- [x] Time-resolved decoding: slide decoder across 10 × 50ms bins (0–500ms)
- [x] Identify OFF-response confound in 200–400ms window (D012)
- [x] Re-test with 400–750ms clean window — VISp still dominant
- [ ] Extended time-resolved (0–750ms) — in progress
- [ ] Apply PCA visualization
- [ ] Full 1,000-permutation run on clean window

**Key finding:** H3 rejected on pilot session. VISp decodes better than VISam in all tested windows (200–400ms: 97% vs 80%; 400–750ms: 90% vs 75%). The OFF-response confound was identified and eliminated, but VISp's advantage persists. This is potentially consistent with prediction error theory (V1 carries PE = 0 − prediction, which is large) or stimulus-specific adaptation. See D012.

**Go/no-go:** Both areas decode well above chance — the signal is real. The question has pivoted from "does VISam > VISp?" to "why does VISp dominate, and does this replicate?"

**Deliverable:** `03_decode.py` producing accuracy scores, null distributions, p-values, time-resolved curves. ✅

---

## Phase 4: Multi-Session Validation
**Status: NOT STARTED**

- [ ] Run extraction + decoding on 5 pilot sessions
- [ ] Aggregate VISp vs. VISam accuracy across sessions (paired Wilcoxon or permutation)
- [ ] Check consistency: does VISam > VISp hold across mice/genotypes?
- [ ] Report effect sizes with confidence intervals

**Deliverable:** Cross-session summary statistics and paired comparison.

---

## Phase 5: Visualization & Interpretation
**Status: NOT STARTED**

- [ ] Plot decoding accuracy vs. time (VISp vs. VISam on same axes, with SEM)
- [ ] Plot null distributions with observed accuracy marked
- [ ] PCA trajectory plots for omission vs. expected trials
- [ ] Generate summary figure suitable for a poster or short report

**Deliverable:** `04_visualize.py` and figures in `results/`.

---

## Phase 6 (Optional): Extensions
- [ ] Infer expected image identity from preceding trial → attempt H1 (multi-class)
- [ ] Test familiar vs. novel image split (is_image_novel) — prediction strength difference?
- [ ] Test active vs. passive blocks separately
- [ ] Add LFP spectral features (gamma/beta) as alternative decoder input
- [ ] Pool across sessions with alignment strategy (e.g., CCA or Procrustes)
- [ ] Test additional areas (VISpm, VISal) available in the dataset
- [ ] Compare omission decoding with novel-stimulus decoding
- [ ] Write up as a short technical report or blog post

---

## Timeline Estimate

| Phase | Effort | Status |
|---|---|---|
| Phase 0 | ✅ Done | Complete |
| Phase 1 | ✅ Done | Complete |
| Phase 2 | ✅ Pilot done | 1/5 sessions extracted |
| Phase 3 | 1–2 days | Next up |
| Phase 4 | 2–3 days | After Phase 3 validates on pilot |
| Phase 5 | 1–2 days | After Phase 4 |
| **Total** | **~1–2 weeks remaining** (part-time) | |