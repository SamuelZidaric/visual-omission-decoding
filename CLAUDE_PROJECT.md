# Claude Project Context: Neuro Omission Decoding

## Who I Am
Samuel Zidarič. Data engineer at Infordata Sistemi (Trieste). MSc Neuroscience (University of Trieste). Fluent in Python, SQL, data pipelines. This is a personal computational neuroscience side project.

## The Project
Decoding pure negative prediction errors (omitted stimulus responses) from mouse visual cortex spiking data, comparing primary visual cortex (V1 / VISp) vs. anteromedial area (AM / VISam).

**Dataset:** Allen Brain Observatory Visual Behavior Neuropixels (open access via `allensdk`).

**Core question:** Does a classifier decode omission vs. expected trials better in VISam than VISp? Is there a latency difference?

## What's Been Done
- Literature review: 9 papers collected (see LITERATURE.md). Key finding: omission responses exist in V1, so the question is about signal quality/timing differences across areas, not presence/absence.
- Dataset feasibility validated: 99 sessions with simultaneous VISp + VISam, median ~50 high-quality units per area.
- Design decisions locked (see DECISIONS.md): spikes only, within-session analysis, permutation testing, linear classifiers.

## How to Help Me
- **Code:** Be precise, production-oriented. I'm senior-level Python/SQL. Skip beginner explanations. Draft working solutions, not pseudocode.
- **Neuroscience:** I have domain knowledge. Don't over-explain basic concepts. Challenge my biological reasoning if it has gaps.
- **Writing:** Professional but accessible. I value clarity over formality. Help me be concise.
- **Approach:** Be direct. If my plan has a flaw, say so. Don't validate — help me think better.

## Technical Environment
- Python 3.9+ with `allensdk`, `numpy`, `pandas`, `scikit-learn`, `matplotlib`
- Data lives in NWB files (~3.5 GB per session) cached locally
- Working on Windows (PowerShell), also comfortable with Linux
- Project folder: `C:\Users\samuel\Desktop\neuro_projects\` (local) or wherever cloned

## Key Constraints
- ~240 omission trials per session vs. ~4500 expected → must undersample for balance
- Within-session analysis only (no cross-session pooling for v1)
- Significance via permutation testing (p < 0.01, 1000 shuffles)
- Quality thresholds: isi_violations < 0.5, amplitude_cutoff < 0.1, presence_ratio > 0.95

## Current Phase
See ROADMAP.md for status. Currently: Phase 0 complete, Phase 1 (hypothesis lock-in) in progress.

## File Structure
```
README.md          — project overview
ROADMAP.md         — phased plan with go/no-go checkpoints
LITERATURE.md      — paper summaries and synthesis
DECISIONS.md       — decision log with rationale
CLAUDE_PROJECT.md  — this file (Claude context)
requirements.txt   — Python dependencies
scripts/           — numbered pipeline scripts
notebooks/         — exploratory Jupyter notebooks
data/              — cached Allen data (gitignored)
results/           — figures and outputs
```