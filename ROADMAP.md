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
- [x] Identify that omission responses exist in V1 (literature says yes, reframes hypothesis)
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

**Key finding:** H3 rejected on pilot session. VISp decodes better than VISam in all tested windows (200–400ms: 97% vs 80%; 400–750ms: 90% vs 75%). The OFF-response confound was identified and eliminated, but VISp's advantage persists. This is potentially consistent with prediction error theory or stimulus-specific adaptation. See D012.

**Go/no-go:** Both areas decode well above chance — the signal is real. The question has pivoted from "does VISam > VISp?" to "why does VISp dominate, and does this replicate?"

**Deliverable:** `04_decode.py` producing accuracy scores, null distributions, p-values, time-resolved curves. ✅

---

## Phase 4: Multi-Session Validation ✅
**Status: COMPLETE (2026-03-30)**

- [x] Select 5 sessions maximizing genotype/mouse diversity (2 SST, 1 VIP, 2 Slc17a7, 5 unique mice)
- [x] Extract spikes: 400–750ms clean window (D012) + 0–500ms time-resolved
- [x] Decode per session: logistic regression, 100 permutations, 10× undersample repeats
- [x] Aggregate paired VISp vs. VISam accuracies across sessions
- [x] Run paired statistical tests (Wilcoxon signed-rank + sign-flip permutation + sign test)
- [x] Report effect sizes and per-session covariate table
- [x] Scale to n=10 sessions via `--resume` incremental pipeline (D014)

**Key results (400–750ms clean window, n=10 sessions):**

| Session | Genotype | Mouse | VISp | VISam | Diff |
|---|---|---|---|---|---|
| 1115077618 | SST | 570299 | 0.930 | 0.836 | −0.095 |
| 1111013640 | VIP | 568963 | 0.954 | 0.868 | −0.085 |
| 1119946360 | Slc17a7 | 578003 | 0.944 | 0.854 | −0.090 |
| 1115086689 | SST | 574078 | 0.951 | 0.848 | −0.103 |
| 1116941914 | Slc17a7 | 576323 | 0.920 | 0.881 | −0.039 |
| 1108334384 | SST | 570301 | 0.915 | 0.719 | −0.196 |
| 1152632711 | VIP | 599294 | 0.900 | 0.858 | −0.042 |
| 1099598937 | Slc17a7 | 560962 | 0.870 | 0.863 | −0.007 |
| 1067588044 | Slc17a7 | 544836 | 0.940 | 0.863 | −0.077 |
| 1139846596 | Slc17a7 | 585329 | 0.936 | 0.910 | −0.025 |

- **VISp mean:** 0.926 ± 0.026, **VISam mean:** 0.850 ± 0.050
- **VISp > VISam in 10/10 sessions** across 3 genotypes, 8 mice
- **Cohen's d:** −1.42 (large effect)
- **Wilcoxon p:** 0.0020, **Permutation p:** 0.0016, **Sign test p:** 0.0010
- All three tests significant at p < 0.01
- All 20 individual per-area permutation tests significant (p = 0.0099)

**Notable observations:**
- Session 1099598937 (Slc17a7): near-tie (VISp 0.870, VISam 0.863). VISp had unusually low mean firing rate (2.7 Hz). Effect survives.
- Session 1108334384 (SST): largest gap (−0.196). VISam had only 56 units — low unit count likely contributed.
- Session 1119946360: VISam had *more* units (120) than VISp (110), yet VISp still won by 9 points — natural control for unit-count confound.

**Go/no-go:** PASSED. H3 definitively rejected. VISp carries a more decodable persistent signal than VISam across all tested conditions. All three non-parametric tests converge at p < 0.01.

**Deliverable:** `05_multi_session.py` (with `--resume` support), `results/multi_session/multi_session_results.json`, `results/multi_session/multi_session_summary.png` ✅

---

## Phase 5: Familiar vs. Novel — Learned Prediction Test ✅
**Status: COMPLETE (2026-03-30)**

**Goal:** Determine whether the persistent 400–750ms signal is a *learned* prediction or a hardwired property of V1 circuitry, using a within-mouse 2×2 repeated-measures design (Area × Experience).

**Design:**
The Allen VBN dataset recorded each mouse twice: once with its trained image set (Familiar, `experience_level = "Familiar"`) and once with a novel set (Novel, `prior_exposures_to_image_set = 0`). Novel sessions also have `prior_exposures_to_omissions = 0`, meaning the mouse has no statistical prior for either the images or the omissions themselves.

9 of our 10 mice have a matched novel session with adequate VISp + VISam unit counts. Mouse 585329 excluded (novel session has only 17 VISam units).

**Results — a double dissociation:**
- **VISp:** 92.5% → 90.1% (Δ = −2.4%, 7/9 mice drop, Wilcoxon p = 0.039). Largely experience-independent.
- **VISam:** 84.3% → 76.3% (Δ = −8.0%, 8/9 mice drop, Wilcoxon p = 0.012). Strongly experience-dependent.
- **Interaction:** VISp drops LESS than VISam (p = 0.039). Different computational roles.

**Interpretation:** V1 encodes a temporal prediction error ("something was supposed to happen now") that doesn't require learned image statistics — the task rhythm is enough. AM encodes a content-dependent expectation that requires prior experience with the specific images. This dissociation maps onto distinct levels of the predictive hierarchy: temporal prediction (V1) vs. content prediction (AM).

- [x] Check familiar/novel trial counts — all 10 sessions are Familiar; `is_image_novel` is `<NA>` on omission rows
- [x] Query session metadata for novel-image sessions — 47 viable novel sessions with VISp + VISam
- [x] Identify within-mouse pairs — 9 mice have matched Familiar + Novel sessions
- [x] Run 400–750ms extraction + decoding on 9 novel sessions (`07_paired_novelty.py`)
- [x] Compute within-mouse deltas (Familiar → Novel) per area
- [x] Statistical tests on deltas (Wilcoxon, sign test, permutation)
- [x] Test Area × Experience interaction
- [x] Generate paired slope plots

**Deliverable:** `07_paired_novelty.py`, `results/novelty_comparison/paired_novelty_results.json`, `results/novelty_comparison/paired_novelty_results.png` ✅

---

## Phase 6: Controls & Publication Prep ✅
**Status: CORE COMPLETE (2026-03-30)**

- [x] **Unit-matched control:** Randomly downsampled VISp to match VISam unit count per session (20 random draws). VISp still better in 9/10 sessions. Wilcoxon p = 0.004, Cohen's d = −1.49 (actually *increased* after matching — unit disparity was adding noise, not driving the effect). Session 1099598937 flipped by 0.007 — the original near-tie. `08_unit_matched_control.py` ✅
- [ ] **1,000-permutation final run:** Optional. 100-permutation runs already hit p-value floor.
- [ ] **Active vs. passive blocks:** Deferred. Would test whether temporal prediction requires engagement.
- [ ] **Publication-quality figures:** To be generated during paper writing.
- [ ] **Paper draft:** Abstract drafted. Short report format (~2500 words) targeting bioRxiv → eLife.

---

## Phase 7 (Optional): Extensions
- [ ] Infer expected image identity from preceding trial → attempt H1 (multi-class)
- [ ] Add LFP spectral features (gamma/beta) as alternative decoder input
- [ ] Pool across sessions with alignment strategy (e.g., CCA or Procrustes)
- [ ] Test additional areas (VISpm, VISal) available in the dataset
- [ ] Compare omission decoding with novel-stimulus decoding
- [ ] Write up as a short technical report or preprint

---

## Timeline Estimate

| Phase | Effort | Status |
|---|---|---|
| Phase 0 | ✅ Done | Complete |
| Phase 1 | ✅ Done | Complete |
| Phase 2 | ✅ Done | Complete (10+ sessions extracted) |
| Phase 3 | ✅ Done | Complete (pilot + 10-session replication) |
| Phase 4 | ✅ Done | Complete (VISp > VISam, 10/10 sessions, p < 0.01) |
| Phase 5 | ✅ Done | Complete (Familiar vs. Novel dissociation, p = 0.039) |
| Phase 6 | ✅ Core done | Unit-matched control complete. Paper writing next. |
| **Remaining** | **Paper writing** | bioRxiv preprint → eLife submission |