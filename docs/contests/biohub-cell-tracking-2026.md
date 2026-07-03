# Biohub Cell Tracking During Development 2026

Status: preparation only. Do not claim official participation until the Kaggle rules are accepted from the submitting account.

Verification date: 2026-07-03

## Source Snapshot

- Official competition: https://www.kaggle.com/competitions/biohub-cell-tracking-during-development
- Rules page: https://www.kaggle.com/competitions/biohub-cell-tracking-during-development/rules
- Email/Kaggle launch summary: $60,000 prize pool, entry deadline 2026-09-22.

## Project Fit

Best project base: `Quantum_BIO_LLMs` plus P2PCLAW evidence logging.

This is not a scientific-paper-generation challenge. It is a 3D biological image tracking challenge. The credible contribution is a reproducible bioimage pipeline:

1. load official 3D time-lapse microscopy data,
2. detect candidate cell centers or masks,
3. link cells through time,
4. identify divisions,
5. output lineage tracks in the required Kaggle format,
6. log experiments and failure cases.

## Baseline Architecture

```text
biohub-cell-tracking/
  README.md
  notebooks/
    00_data_smoke_test.ipynb
    01_baseline_tracking.ipynb
  src/
    data.py
    preprocessing.py
    detection.py
    linking.py
    lineage.py
    submission.py
  experiments/
    README.md
  reports/
    error-analysis.md
```

## Honest Boundaries

- Do not download or redistribute Kaggle data outside Kaggle's terms.
- Do not submit until rules are accepted from the account owner.
- Do not claim leaderboard performance before a real submission exists.
- Do not reuse copyrighted biological imagery in marketing materials.
- Treat `Quantum_BIO_LLMs` as documentation/analysis support unless a real image model is implemented.

## First Autonomous Work Available Before Kaggle Login

- Prepare repository structure.
- Write a data-agnostic baseline interface.
- Prepare an experiment log template.
- Prepare a submission checklist.
- Prepare a README that clearly says data and submission require Kaggle login/rules acceptance.

## Manual Requirements

- Accept Kaggle rules.
- Download official data through Kaggle.
- Confirm metric and submission schema from the competition notebooks/rules.
- Run at least one end-to-end local smoke test before any submission.
