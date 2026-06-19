# Kaggle Pokemon TCG AI Battle Challenge 2026

Status: preparation only. Do not claim official participation until the Kaggle rules are accepted from the account that will submit.

## Source Snapshot

- Official Simulation competition: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- Official Strategy competition: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy/overview
- Verification date: 2026-06-19

## Dates To Track

| Track | Date | Meaning |
| --- | ---: | --- |
| Simulation | 2026-08-09 | Team merger / entry deadline shown by Kaggle search result and launch email. |
| Simulation | 2026-08-16 | Final submission deadline shown by Kaggle search result. |
| Strategy | 2026-09-06 | Entry deadline from Kaggle launch email and public launch posts. |

Use the official Kaggle pages as the source of truth before submission because competition dates can change.

## Best Fit For This Repository

OpenCLAW/P2PCLAW is most relevant as an agent orchestration and evaluation harness, not as a direct Pokemon TCG rules engine. The useful contribution is a reproducible agent loop:

1. observe game state,
2. normalize hidden/public information into a compact state object,
3. score legal actions with deterministic heuristics,
4. optionally call a local planner for long-horizon reasoning,
5. log decisions for the Strategy Category report.

## Proposed Baseline Agent Shape

```text
agent/
  policy.py              deterministic action scoring
  state_encoder.py       converts simulator state into a stable feature object
  rollout.py             optional local search / simulation hook
  telemetry.py           writes decision traces for the strategy report
notebooks/
  smoke_test.ipynb       validates the competition environment after joining
reports/
  strategy-outline.md    rationale, ablations, stability notes
```

## Engineering Guardrails

- Keep the first baseline deterministic and dependency-light.
- Do not scrape or bundle copyrighted card assets.
- Do not hard-code private competition tokens or Kaggle credentials.
- Store match traces without personal data.
- Separate simulator adapters from the policy so the policy can be tested locally.
- Treat the Strategy Category as a research report backed by logs, not marketing copy.

## First Implementation Checklist

- [ ] Accept Kaggle rules manually from the submitting account.
- [ ] Download the official environment/data through Kaggle.
- [ ] Identify the required submission interface.
- [ ] Build one deterministic legal-action baseline.
- [ ] Add a smoke test that runs a single local match or simulator step.
- [ ] Add decision logging for state, legal actions, selected action, and score reason.
- [ ] Run at least five local matches before any public submission.
- [ ] Only then prepare Strategy Category text.
