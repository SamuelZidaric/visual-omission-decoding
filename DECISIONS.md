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

### PENDING DECISIONS

- **Multi-session validation:** Does VISp > VISam replicate across sessions, genotypes, and familiar vs. novel conditions? (Critical before any conclusions.)
- **Adaptation vs. prediction error:** Can we disentangle these? Possible approach: compare decoding accuracy for familiar images (strong adaptation + strong prediction) vs. novel images (weak adaptation + weak prediction). If adaptation dominates, familiar > novel. If prediction error dominates, familiar > novel too but for a different reason — need careful thought here.
- **Active vs. passive blocks:** Prediction strength may differ between active engagement and passive viewing. Test separately.
- **Extended time-resolved (0–750ms):** Pending — will show the full decay curve through the inter-stimulus interval.
- **Minimum unit threshold per session:** Tentatively 20 units in both VISp and VISam. May adjust.