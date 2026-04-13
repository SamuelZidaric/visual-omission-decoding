# Publication Plan

## Paper Summary

**Working title:** Dissociable omission signals across the mouse visual hierarchy: experience-independent temporal prediction in V1 and experience-dependent content expectation in area AM

**Format:** Short report (~2500 words), 3 main figures, 3 supplemental figures

**Venue:** bioRxiv preprint → eLife submission

**Authors:** Samuel Zidarič (+ any collaborators/advisors to be determined)

**License:** CC-BY 4.0 (paper), MIT (code)

---

## Three Core Findings

1. **VISp > VISam in the clean window (400–750ms)**
   - n=10 sessions, 8 mice, 3 genotypes
   - Wilcoxon p = 0.002, Cohen's d = −1.42
   - 10/10 sessions concordant

2. **Double dissociation: VISp = experience-independent, VISam = experience-dependent**
   - Within-mouse paired design, n=9 mice
   - VISp: 92.5% → 90.1% (Δ = −2.4%, p = 0.039)
   - VISam: 84.3% → 76.3% (Δ = −8.0%, p = 0.012)
   - Interaction: p = 0.039

3. **Unit-matched control confirms the effect is biological**
   - 9/10 sessions after matching, Wilcoxon p = 0.004
   - Cohen's d = −1.49 (increased after matching)

---

## Paper Structure

### Introduction (~400 words)
- Predictive processing: brain generates expectations, signals surprise
- Omissions as a clean probe: no bottom-up input, pure internal signal
- V1 omission responses exist (Price & Gavornik 2025, Keller et al. 2024)
- Open question: what are the distinct roles of V1 vs. higher-order areas?
- This study: population decoding of omission responses in VISp vs. VISam

### Results (~1000 words)
- **Result 1:** Late-window (400–750ms) decoding — VISp > VISam across 10 sessions
  - Motivate the window choice: time-resolved decoding across all 10 sessions confirmed that VISp accuracy remained elevated beyond the OFF-response window while VISam decayed toward chance (Supplemental Figure S1), justifying the 400–750ms focus
  - Present the 10-session table and paired statistics
  - Reference unit-matched control (detail in supplement)
- **Result 2:** Familiar vs. novel — the double dissociation
  - Within-mouse design explanation
  - VISp barely drops, VISam collapses
  - Interaction test

### Discussion (~600 words)
- "Rhythm vs. Content" interpretation: V1 = temporal PE, AM = content expectation
- Relation to predictive coding hierarchy (Rao & Ballard 1999)
- Why this argues against pure SSA (SSA should be experience-dependent in both areas)
- Relation to Chao et al. 2025 (V1 omission signals mixed with OFF-activity — we confirm and extend)
- Limitations: binary decoder, single time bin, active block only
- Future: active vs. passive, finer temporal resolution, additional areas

### Methods (~800 words)
- Dataset: Allen VBN, sessions selected for genotype/mouse diversity
- Spike extraction: quality filters, trial selection, binning
- Decoding: LogisticRegressionCV, undersampling, CV, permutation test
- Multi-session statistics: Wilcoxon, sign test, permutation
- Novelty comparison: within-mouse paired design
- Unit-matched control: random unit subsampling procedure

---

## Figure Plan

### Figure 1: Task Design & Motivation
- Panel A: Change detection task schematic with omission timing
- Panel B: Example PSTHs (VISp/VISam, omission/expected) with annotated windows
- Panel C: Time-resolved decoding (one example session) motivating the 400–750ms choice

### Figure 2: VISp > VISam Across Sessions
- Panel A: Paired dot plot (10 sessions, color by genotype)
- Panel B: Per-session difference bars (all negative)
- Stats: Wilcoxon p = 0.002, d = −1.42

### Figure 3: Familiar vs. Novel Double Dissociation
- Panel A: VISp slope plot (Familiar → Novel, 9 mice) — minimal drop
- Panel B: VISam slope plot — substantial drop
- Panel C: Interaction scatter (VISp delta vs. VISam delta)
- Stats: Interaction p = 0.039

### Supplemental Figures
- S1: Time-resolved decoding across all 10 sessions (mean ± SEM, 0–500ms, 50ms bins). Descriptive — no formal bin-by-bin statistics. Motivates the 400–750ms window choice by showing VISp stays elevated while VISam decays.
- S2: Unit-matched control table and comparison
- S3: Per-session null distributions

---

## Open Science Checklist

### Code (GitHub)
- [ ] Clean up repo: remove scratch files, check `.gitignore`
- [ ] Update README.md with final results summary and reproduction instructions
- [ ] Add `CITATION.cff` file for proper citation
- [ ] Verify all scripts run from project root with `--cache_dir` flag
- [ ] Add `requirements.txt` or `environment.yml` with pinned versions
- [ ] Tag release: `v1.0.0` once paper is submitted to bioRxiv
- [ ] Repo: `github.com/SamuelZidaric/visual-omission-decoding`

### Data & Results (Zenodo)
- [ ] Create Zenodo deposit linked to GitHub release
- [ ] Include in deposit:
  - `results/multi_session/multi_session_results.json` (10-session familiar baseline)
  - `results/novelty_comparison/paired_novelty_results.json` (within-mouse novelty)
  - `results/unit_matched_control/unit_matched_results.json` (control analysis)
  - All generated figures (PNG, 300 DPI)
  - A README explaining the deposit contents
- [ ] Do NOT include raw NWB files (they're Allen's data, hosted on AWS)
- [ ] Do NOT include spike matrices (reproducible from scripts + Allen cache)
- [ ] Zenodo DOI → reference in paper's Data Availability statement

### Data Availability Statement (for paper)
```
All neural recordings are from the Allen Brain Observatory Visual Behavior
Neuropixels dataset, publicly available via the AllenSDK
(https://allensdk.readthedocs.io/en/latest/visual_behavior_neuropixels.html).
Analysis code is available at https://github.com/SamuelZidaric/visual-omission-decoding
(MIT license). Derived results and figures are archived at [Zenodo DOI].
```

### bioRxiv Submission
- [ ] Convert paper to PDF (from LaTeX, Word, or Markdown)
- [ ] Register bioRxiv account if needed
- [ ] Submit as "New Results" under Neuroscience
- [ ] License: CC-BY 4.0
- [ ] Link GitHub repo and Zenodo DOI in the paper

### eLife Submission
- [ ] eLife now reviews preprints — submit via "Reviewed Preprints" track
- [ ] Point to the bioRxiv preprint
- [ ] Cover letter (~200 words): why this is significant, the double dissociation is novel
- [ ] Suggested reviewers: authors of Price & Gavornik 2025, Chao et al. 2025, Keller et al. 2024

---

## Key Parameters to Document in Methods

| Parameter | Value |
|-----------|-------|
| Dataset | Allen VBN, 153 sessions, 81 mice |
| Areas | VISp (V1), VISam (AM) |
| Analysis window | 400–750ms post-stimulus onset |
| Bin width | 350ms (single bin) |
| Unit quality | ISI violations < 0.5, amplitude cutoff < 0.1, presence ratio > 0.95 |
| Min units/area | 20 |
| Trial selection | Active block, non-change, non-omission (for expected class) |
| Class balance | 10× random undersampling of expected to match omission count |
| Classifier | LogisticRegressionCV, L2, Cs=10, solver=lbfgs, max_iter=1000 |
| Cross-validation | Stratified 5-fold |
| Permutation test | 100 shuffles per area per session |
| Multi-session stats | Wilcoxon signed-rank, sign-flip permutation (10,000), one-sided sign test |
| Unit matching | 20 random unit subsamples, decode each, report mean |
| Random seed | 42 |
| Familiar sessions | 10 (experience_level = "Familiar") |
| Novel sessions | 9 matched (experience_level = "Novel", prior_exposures = 0) |

---

## Key Citations

1. Price & Gavornik (2025) — V1 L2/3 omission responses, temporal expectation
2. Keller, Mrsic-Flogel et al. (2024) — Thalamocortical PE circuit in V1
3. Chao et al. (2025) — Brain-wide omission diversity, V1 signals mixed with OFF
4. Rao & Ballard (1999) — Predictive coding hierarchy
5. Friston (2005) — Free energy / predictive processing framework
6. Allen Institute VBN dataset citation (bioRxiv 2025)

---

## Timeline

| Task | Estimate | Notes |
|------|----------|-------|
| GitHub cleanup | 1 hour | README, CITATION.cff, requirements.txt |
| Publication-quality figures | 2–3 hours | Regenerate at 300 DPI, consistent style |
| Paper draft (short report) | 1–2 days | ~2500 words |
| Internal review / revision | 1 day | Re-read, tighten prose |
| bioRxiv submission | 30 minutes | Upload PDF + supplement |
| Zenodo archive | 30 minutes | Link to GitHub release |
| eLife submission | 1 hour | Cover letter + point to preprint |
| **Total** | **~3–5 days** | Part-time, assuming no major revisions |