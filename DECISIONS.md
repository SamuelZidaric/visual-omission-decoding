# Decision Log

Every non-trivial design choice, with rationale and date. If a decision is revisited, the old entry stays (with SUPERSEDED tag) and a new one is added.

---

### D001: Topic Selection (2026-03-29)
**Decision:** Decode omission responses (pure negative prediction errors) across V1 vs. AM using Allen VBN Neuropixels data.
**Rationale:** Omitted stimuli isolate internally-generated expectation from sensory processing. Allen VBN is open, well-documented, and includes an omission paradigm (~5% of flashes). Topic is at the center of an active debate (2024–2026).
**Alternatives rejected:** Decoding novel stimuli (messy — mixes surprise + sensory response). LFP spectral analysis (deferred to v2). Connectomics (wrong scale for a side project).

### D002: Modality — Spikes Only (2026-03-29)
**Decision:** Use spiking activity (firing rates) for v1. Ignore LFP entirely.
**Rationale:** Spikes are conceptually cleaner, easier to bin into discrete time windows, and map directly onto standard decoding pipelines. Adding LFP doubles preprocessing and feature space. Can revisit if spike decoding fails.

### D003: Success Criterion — Permutation Testing (2026-03-29)
**Decision:** Significance defined as decoding accuracy above 99th percentile of a 1,000-shuffle null distribution (p < 0.01). No fixed accuracy threshold.
**Rationale:** With imbalanced data and small trial counts, an arbitrary accuracy number (e.g., "70%") is meaningless. Permutation testing gives a principled null. The 65–80% range cited by Gemini is from generic visual decoding, not omission-specific — no reliable baseline exists yet.

### D004: Within-Session Analysis (2026-03-29)
**Decision:** Run decoding within each session independently (not pooling across sessions).
**Rationale:** Cross-session pooling introduces neural variability from different mice, probe placements, and behavioral states. Within-session keeps the decoder clean. Pool later (Phase 6) with alignment methods if needed.

### D005: Class Balancing — Undersample Expected Trials (2026-03-29)
**Decision:** Undersample the majority class (expected trials) to match the minority class (omission trials, ~240 per session), creating a balanced ~480-trial dataset per session.
**Rationale:** 5% omission rate → ~240 omissions vs. ~4500 expected trials. Training on imbalanced data biases the classifier toward the majority class. Undersampling is the simplest approach; SMOTE or oversampling are inappropriate for neural data.

### D006: Classifier Choice — Linear SVM or Logistic Regression (2026-03-29)
**Decision:** Start with logistic regression and linear SVM. No deep learning.
**Rationale:** With ~480 trials and ~50 features (units), a linear model is appropriately sized. Nonlinear models risk overfitting. Logistic regression gives interpretable weights (which neurons contribute most). SVM is standard in the field.

### D007: Quality Filters for Units (2026-03-29)
**Decision:** isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.95.
**Rationale:** Allen Institute standard thresholds. Strict but ensures clean single-unit data. presence_ratio > 0.95 may be relaxed if AM unit counts drop too low in some sessions. Monitor during Phase 2.

### SUPERSEDED — D008: Hypothesis Reframe (2026-03-29)
**Decision:** The question is NOT "do omission responses exist in V1?" (literature says yes). The question is "does decoding accuracy/latency differ between VISp and VISam?"
**Rationale:** Literature review showed V1 has omission signals. The interesting comparison is quantitative — is the signal cleaner, earlier, or more decodable in higher areas?
**Superseded by:** D009.

### D009: Refined Hypothesis — Prediction vs. Prediction Error (2026-03-29)
**Decision:** Reframe the hypothesis using canonical predictive coding terminology (Rao & Ballard 1999, Friston 2005). Under this framework:

- **VISam** (higher-order) generates the top-down **prediction** — the internal expectation of which image should appear. During omissions, VISam activity reflects the prediction itself.
- **VISp** (primary visual cortex) computes the **prediction error** — the mismatch between the top-down prediction and the (absent) bottom-up input. During omissions, VISp activity reflects PE = 0 − Prediction.

Therefore, the revised hypotheses are:

- **H1 (primary):** Late-window omission activity (200–400ms) in VISam carries a more decodable **stimulus-specific expectation signal** than VISp. A decoder may be able to distinguish which image was omitted from VISam population activity, because VISam holds the image-specific prediction.
- **H2 (secondary):** VISp omission activity encodes a sharper but less stimulus-specific **mismatch signal** — potentially with an earlier onset but without retaining the identity of the expected image.
- **H3 (tertiary, if image identity is not available in omission metadata):** Binary omission-vs-expected decoding from late-window activity (200–400ms, after the trivial sensory response has decayed) is higher in VISam than VISp, reflecting a cleaner internally-generated prediction signal.

**Rationale:** The initial framing (D008) conflated "prediction" and "prediction error." Under predictive coding, predictions flow top-down (AM → V1) and prediction errors flow bottom-up (V1 → AM). Omission trials, where sensory input = 0, isolate the prediction component in VISam and the error component in VISp. This distinction makes the hypothesis sharper and better grounded in theory.

**Note:** H1 feasibility depends on whether omission trials in the Allen VBN dataset retain the identity of the image that would have been shown. Checking via check_omission_per_image.py (2026-03-29).

### D010: Avoid the Trivial Decoder (2026-03-29)
**Decision:** The primary analysis must use a **late time window** (200–400ms post-omission onset) to avoid trivially decoding the presence/absence of a visual response.

**Rationale:** Diagnostic PSTHs (session 1064644573) confirm that expected trials show a massive visual response (30–90 Hz peak) within 50–100ms of stimulus onset, while omission trials remain at baseline. Any decoder using the 0–250ms window will achieve near-perfect accuracy by simply detecting "did a visual response occur?" This is scientifically uninteresting.

The interesting signal is the late-window activity during omissions: internally-generated expectation signals that persist after the sensory transient has decayed. The 200–400ms window captures this while avoiding both the onset transient and the stimulus offset response (~250ms).

A secondary analysis using the full 0–500ms window with 50ms sliding bins will produce a time-resolved decoding curve — showing when decoding accuracy rises above chance in each area. This latency comparison is informative regardless of the late-window result.

---

### D011: Image-Identity Decoding — Not Feasible (2026-03-29)
**Decision:** Fall back to H3 (binary omission-vs-expected decoding). H1 (multi-class image-identity from omissions) is not possible with the Allen VBN dataset.

**Evidence:** `check_omission_per_image.py` confirms that omission rows in `stimulus_presentations` have `image_name = "omitted"` — the identity of the expected image is not recorded. All 356 omission trials share the same label.

**Implication:** The primary analysis is now H3: train a binary decoder (omission vs. expected) on late-window activity (200–400ms), compare decoding accuracy between VISam and VISp across sessions. The comparison tests whether the internally-generated prediction signal is more decodable in the higher-order area.

**Possible extension:** Infer expected image identity from the preceding stimulus in the sequence (the omitted flash should have repeated the previous image in most cases). This would recover H1 but adds assumptions about the task structure. Deferred to Phase 6.

**Bonus finding:** The `is_image_novel` column cleanly separates familiar (trained) vs. novel images. Prediction strength may differ — test as a secondary analysis (familiar-only omissions vs. novel-only omissions).

---

### D010: Avoid the Trivial Decoder (2026-03-29)
**Decision:** The primary analysis must use a **late time window** (200–400ms post-omission onset) to avoid trivially decoding the presence/absence of a visual response.

**Rationale:** Diagnostic PSTHs (session 1064644573) confirm that expected trials show a massive visual response (30–90 Hz peak) within 50–100ms of stimulus onset, while omission trials remain at baseline. Any decoder using the 0–250ms window will achieve near-perfect accuracy by simply detecting "did a visual response occur?" This is scientifically uninteresting.

The interesting signal is the late-window activity during omissions: internally-generated expectation signals that persist after the sensory transient has decayed. The 200–400ms window captures this while avoiding both the onset transient and the stimulus offset response (~250ms).

A secondary analysis using the full 0–500ms window with 50ms sliding bins will produce a time-resolved decoding curve — showing when decoding accuracy rises above chance in each area. This latency comparison is informative regardless of the late-window result.

**SUPERSEDED by D012** — 200–400ms still contaminated by OFF-response.

---

### D012: The OFF-Response Confound and the 400–750ms Window (2026-03-29)
**Decision:** Shift the primary analysis window from 200–400ms to **400–750ms** to eliminate the stimulus offset (OFF) response confound.

**Evidence:**
- R007: VISp decoded at 97.4% in the 200–400ms window — too high. The time-resolved analysis (R008) revealed a second decoding peak at 275ms, coinciding with the stimulus offset at 250ms.
- In the Allen VBN task, images are ON for 250ms. At 250ms, the image disappears → V1 neurons with OFF-selectivity fire strongly. Omission trials have no OFF-transient (screen was already gray). The 200–400ms decoder was largely classifying "did an OFF-transient occur?"
- R009: Even at 400–750ms (well past the OFF-response), VISp still decoded at 90% and VISam at 75%. This rules out the OFF-response as the sole explanation — there is a genuine persistent signal.

**Revised interpretation:** VISp outperforming VISam in the clean late window (400–750ms) is either:
1. **Prediction error persistence:** Under predictive coding, V1 computes PE = sensory input − prediction. During omissions, PE = 0 − prediction = −prediction. This is a large, structured signal that may persist. V1 carries the error; VISam carries the prediction itself, which is similar between omission and expected trials (AM predicts in both cases).
2. **Stimulus-specific adaptation:** Expected trials carry neural adaptation from the just-presented image; omission trials don't. V1 shows stronger adaptation effects than higher areas.
3. **Combination of both.** Disentangling these requires additional analyses (see pending decisions).

**Impact on H3:** H3 as originally framed (VISam > VISp) is rejected on the pilot session. However, the finding that VISp carries a strong, persistent post-stimulus signal during omissions is itself interesting and potentially publishable. The project pivots from "confirming H3" to "characterizing the hierarchy of persistent omission signals."

---

### D013: Multi-Session Validation — VISp > VISam Confirmed (2026-03-30)
**Decision:** The VISp > VISam finding from the pilot (D012) is confirmed across 10 sessions spanning 3 genotypes and 8 unique mice. H3 is definitively rejected.

**Evidence (n=10, 400–750ms clean window):**
- 10 sessions selected for genotype/mouse diversity: 3 SST-IRES-Cre, 2 VIP-IRES-Cre, 5 Slc17a7 (excitatory), 8 unique mice
- VISp mean accuracy: 0.926 ± 0.026; VISam mean accuracy: 0.850 ± 0.050
- VISp > VISam in **10/10 sessions** (differences: −0.007 to −0.196)
- Cohen's d = −1.42 (large); Wilcoxon p = 0.0020; Permutation p = 0.0016; Sign test p = 0.0010
- All three tests significant at p < 0.01
- All 20 individual area-level permutation tests significant (p = 0.0099)
- Result holds across both image sets (G and H) and varied unit counts

**Notable observations:**
- Session 1099598937: near-tie (VISp 0.870, VISam 0.863, diff −0.007). VISp had unusually low mean firing rate (2.7 Hz). Even the weakest session still shows VISp ≥ VISam.
- Session 1108334384: largest gap (−0.196). VISam had only 56 units. Low unit count likely amplified the gap.
- Session 1119946360: VISam had *more* units (120) than VISp (110), yet VISp still won by 9 points. Natural control against the unit-count confound.

**Interpretation:**
The persistent signal in VISp 400–750ms after stimulus onset — when both omission and expected trials are viewing a gray screen — is consistently more decodable than VISam. Under predictive coding, this is consistent with V1 carrying a large, structured prediction error (PE = 0 − prediction = −prediction) that persists beyond the sensory transient, while VISam carries the prediction itself, which is similar between omission and expected conditions (AM predicts in both cases, only the PE differs).

Alternative interpretation: stimulus-specific adaptation (SSA) is stronger in V1 than AM. Expected trials carry residual adaptation from the just-presented image; omission trials don't. This would also produce VISp > VISam decoding without requiring a predictive coding framework. Disentangling PE from SSA requires the familiar vs. novel comparison (D015).

**Neurobiological note on genotype:** Neuropixels records all nearby extracellular spikes regardless of Cre line. The Cre-line labels (SST, VIP, Slc17a7) identify which cell type is opto-taggable, not which neurons enter the decoder. The decoded population is dominated by excitatory pyramidal cells in all sessions. Genotype diversity confirms the finding is not an artifact of a specific transgenic background.

---

### D014: Scale to n=10 via Incremental Resume (2026-03-30)
**Decision:** Extended the multi-session validation from n=5 to n=10 using `--resume` mode in `05_multi_session.py`. The script loads previous results, selects new sessions excluding already-processed ones, seeds diversity tracking from existing genotypes/mice, and merges all results for re-aggregation.

**Rationale:** With n=5, Wilcoxon signed-rank has a minimum p-value of 0.0625 (cannot reach p < 0.05 even with perfect concordance). At n=10, all three tests (Wilcoxon, permutation, sign test) converge at p < 0.01. Cohen's d moved from −3.27 to −1.42 — still large, but the new sessions brought healthy variance (differences ranging from −0.007 to −0.196 vs. the original −0.039 to −0.103).

**Implementation:** `05_multi_session.py --n_sessions 10 --resume` backs up previous results, selects 5 new sessions with diversity-aware greedy picker, processes only the new sessions (~17.5 GB NWB downloads), and produces merged JSON + updated summary figure.

---

### D015: Familiar vs. Novel — Within-Mouse Paired Design (2026-03-30)
**Decision:** Test whether the persistent 400–750ms signal depends on learned image expectations using a within-mouse 2×2 repeated-measures design (Area: VISp vs. VISam × Experience: Familiar vs. Novel).

**Design:**
- The Allen VBN dataset records each mouse with both its trained image set (Familiar, `experience_level = "Familiar"`, `prior_exposures_to_image_set > 0`) and a new set (Novel, `prior_exposures_to_image_set = 0`).
- Novel sessions also have `prior_exposures_to_omissions = 0` — the mouse has no statistical prior for omissions.
- 9 of our 10 mice have a matched novel session with ≥20 quality units in both VISp and VISam. Mouse 585329 excluded (novel session has 17 VISam units, below threshold).
- 47 total viable novel sessions exist in the dataset, so the pool is large.

**Key insight:** The `is_image_novel` column within a session does NOT help — all 10 familiar sessions have 100% familiar trials. The split requires comparing across sessions: one familiar session vs. one novel session per mouse. Within-mouse pairing controls for probe placement, mouse identity, and baseline neural variability.

**Predictions:**
1. **Learned prediction** (PE theory): VISp accuracy drops substantially for novel images. The 400–750ms signal encodes a learned top-down expectation.
2. **Hardwired dynamics** (SSA theory): VISp accuracy stays high for novel images. The signal is intrinsic to V1 circuitry.
3. **Area-specific learning**: One area drops, the other doesn't. Different mechanisms at different levels of the hierarchy.

**Implementation:** `07_paired_novelty.py` — hardcoded 9 mouse→(familiar, novel) session pairs, same 400–750ms extraction + decoding pipeline, within-mouse delta analysis, Wilcoxon/sign/permutation tests, 3-panel slope plot.

---

### D016: Familiar vs. Novel — Double Dissociation (2026-03-30)
**Decision:** The within-mouse familiar vs. novel comparison reveals a functional double dissociation: VISp's omission signal is largely experience-independent, while VISam's is experience-dependent.

**Evidence (n=9 mice, within-mouse paired design):**
- VISp: Familiar 92.5% → Novel 90.1% (Δ = −2.4%, d = −0.71, Wilcoxon p = 0.039)
  - 7/9 mice show a drop, but the drops are small (max −10.2%, most < 3%)
- VISam: Familiar 84.3% → Novel 76.3% (Δ = −8.0%, d = −1.41, Wilcoxon p = 0.012)
  - 8/9 mice show a drop, with substantial decreases (−3.5% to −15.1%)
- Interaction (Area × Experience): VISp drops LESS than VISam (p = 0.039)
- Mouse 570301 (SST): VISam rose +4.0% (novel > familiar), but this mouse had the lowest VISam unit count in the familiar session (56 units, decoding at 71.9%). Signal-to-noise artifact, not biological contradiction.

**Interpretation — "Rhythm vs. Content":**
- VISp encodes a **temporal prediction error**: the task rhythm (250ms ON / 500ms OFF) is learned rapidly even for novel images. When an expected event doesn't occur at the predicted time, V1 generates a mismatch signal. This doesn't require knowledge of *which* image was expected.
- VISam encodes a **content-dependent expectation**: it needs learned image statistics to generate a strong omission representation. With novel images, the internal model is weak, and the signal degrades.

**Implications for SSA vs. PE debate:** Pure stimulus-specific adaptation would predict both areas are experience-dependent (adaptation requires repeated exposure). VISp's experience-independence argues against SSA and favors a temporal expectation mechanism.

---

### D017: Unit-Matched Control — Feature Count Not a Confound (2026-03-30)
**Decision:** The VISp > VISam baseline finding survives unit matching. The effect is not driven by differences in neuron yield between areas.

**Evidence (n=10 sessions, 20 random unit subsamples per session):**
- VISp still better in 9/10 sessions after downsampling to match VISam unit count
- Matched VISp mean: 0.915 ± 0.028; Matched VISam mean: 0.845 ± 0.047
- Mean diff (matched): −0.070; Cohen's d = −1.49 (increased from −1.42 unmatched)
- Wilcoxon p = 0.004; Sign test p = 0.011
- The one "flip" is session 1099598937 — the original near-tie (unmatched diff was −0.007). After matching to 76 units, VISam edged ahead by 0.007. Noise around zero.

**Key insight:** Cohen's d *increased* after matching (−1.42 → −1.49), meaning the unit-count disparity was adding noise, not driving the effect. This is the strongest possible defense against the feature-count critique.

---

### PENDING DECISIONS

- **RESOLVED: Multi-session validation** → D013 → D014. VISp > VISam, 10/10, p < 0.01. ✅
- **RESOLVED: Familiar vs. novel** → D015 (design) → D016 (results). Double dissociation, interaction p = 0.039. ✅
- **RESOLVED: Unit-matched control** → D017. 9/10 sessions, d = −1.49, p = 0.004. ✅
- **Active vs. passive blocks:** Would test if temporal prediction requires behavioral engagement. Deferred — strong extension for follow-up but not required for initial publication.
- **Publication venue:** bioRxiv preprint → eLife submission. Short report format (~2500 words). Open access, open data (Zenodo + GitHub). See PUBLICATION.md.