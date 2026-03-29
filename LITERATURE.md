# Literature

Collected 2026-03-29 via Perplexity search. Focus: omission responses / negative prediction errors in mouse visual cortex (2021–2026).

---

## Paper 1: Price & Gavornik (2025)
- **Title:** Learned response dynamics reflect stimulus timing and encode temporal expectation violations in superficial layers of mouse V1
- **DOI:** https://elifesciences.org/reviewed-preprints/94727
- **Finding:** Omission responses occur in V1 L2/3. After sequence training, omitting a predicted grating element elicits temporally specific elevated activity at the expected onset time. Interpreted as temporal negative prediction error in V1.
- **Method:** Two-photon Ca²⁺ imaging (GCaMP, L2/3 excitatory neurons). Not Neuropixels, not Allen data.
- **Relevance:** Strongest evidence that V1 encodes omissions. Challenges the "omissions only in higher areas" view.

## Paper 2: Keller, Mrsic-Flogel et al. (2024)
- **Title:** Cooperative thalamocortical circuit mechanism for sensory prediction errors
- **DOI:** https://www.nature.com/articles/s41586-024-07851-w
- **Finding:** V1 generates prediction-error signals via thalamocortical disinhibitory circuit in L2/3. Implies omission-type errors can be instantiated locally in V1 (not only higher areas).
- **Method:** Extracellular spiking + optogenetics in V1 and thalamus. Conventional silicon probes.
- **Relevance:** Circuit mechanism for how V1 could produce omission signals. Important for interpretation.

## Paper 3: Audette & Schneider (2025, review)
- **Title:** Auditory cortex neurons that encode negative prediction errors (review citing visual cortex work)
- **DOI:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12212881/
- **Finding:** Review confirms V1 contains neurons with negative mismatch responses during locomotion when visual flow is omitted. Molecularly distinct V1 population responds selectively to omissions.
- **Method:** Cited studies use mix of spiking and LFP. Standard probes.
- **Relevance:** Cross-modal review supporting V1 omission coding.

## Paper 4: Price et al. (2023)
- **Title:** Stimulus-selective response potentiation and temporal prediction errors in deep layers of V1
- **DOI:** See citations in Paper 1
- **Finding:** Deep-layer V1 neurons (L4/5) show enhanced activity when expected transitions are omitted. Extends omission evidence to deeper V1 layers.
- **Method:** Extracellular multi-unit spiking + LFP. Standard probes.
- **Relevance:** Omission responses span V1 layers (L2/3 from Paper 1, L4/5 here).

## Paper 5: Chao et al. (2025)
- **Title:** Diversity of omission responses to visual images across brain-wide cortical and subcortical circuits
- **DOI:** https://www.science.org/doi/10.1126/sciadv.adv5651
- **Finding:** V1 shows omission-like responses, but hippocampus and thalamus host more "pure" omission encoders — cells that fire at expected stimulus time even when they don't respond to the stimulus itself. V1 omission signals are mixed with OFF/expectation-related activity.
- **Method:** Neuropixels-style large-scale multi-region recordings. Closest to our planned approach.
- **Relevance:** KEY PAPER. Most directly comparable methodology. Suggests the V1 vs. higher-area difference is about signal purity, not presence/absence.

## Paper 6: Wang et al. (2025)
- **Title:** Differential modulation of positive and negative prediction errors by stimulus variability
- **DOI:** https://www.nature.com/articles/s42003-025-08797-z
- **Finding:** Somatosensory/PPC focus, but cites positive and negative PE neurons in V1 L2/3. Both V1 and association areas encode PEs, modulated differently by variability.
- **Method:** Extracellular spiking in L2/3 somatosensory + PPC. Standard probes.
- **Relevance:** Peripheral but supports the gradient model of PE coding.

---

## Synthesis

The field has moved beyond "does V1 encode omissions?" (yes, it does). The open questions are:
1. **Signal purity:** Are higher-area omission signals more "pure" (less contaminated by OFF responses)?
2. **Timing:** Do omission signals emerge earlier or later across the hierarchy?
3. **Population structure:** Do omission-encoding neurons form distinct subpopulations?

Our project targets question 1 and potentially 2 via decoding accuracy and time-resolved analysis.

---

## Still Needed
- [ ] Papers reporting actual **decoding accuracies** on omission trials (to set baselines)
- [ ] Papers using the **Allen VBN dataset** specifically for omission analysis
- [ ] The "ubiquitous predictive processing in the spectral domain" eLife 2025 paper (for LFP v2)