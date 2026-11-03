# LIVE AUTONOMOUS COMPETITION OPERATIONS ? 2026-11-03
This is an EXECUTION order from Francisco Angulo de Lafuente, not a request for another plan. Use tools and record verifiable artifacts. Operate from Server-IA. Read your AGENTS.md and the installed cognitiva-hierarchical-competitions skill.

## Immediate run
1. Read /srv/openclaw/competition-state/portfolio.json and competition-triage.json. Audit all already entered competitions BEFORE considering new ones. Prioritize deadlines within 72h (Virtual Cell, AIMO/PAIEC, MIT Solve, KISTI) but VERIFY on official sites first. Avoid duplicate applications.
2. Assign real bounded work: Boss (Fable 5.1) -> Director (Opus 5.5) -> Research and Engineering Leads (Sonnet 5.5) -> up to 10 Haiku 5.5 workers via OpenClaw subagents/flows, if the tools actually allow it. Verify child task IDs and completion receipts. If delegation is not available, perform a smaller single-agent review, record exact blocker and continue with other authorized work.
3. Have workers inspect authoritative contest rules, dates, participant eligibility from Spain, allowed prior code, prizes, submission instructions, official receipts, and project fit. Compare against Agnuxo1 repositories, arXiv, Google Scholar and trustworthy technical repositories. Note what sources were actually opened.
4. For the first run, complete at least ONE official-source-verified contest brief with source URL, time, eligibility, confirmed existing submission status or UNKNOWN, baseline, metric, best foundation repository and a concrete ?24h experiment plan. Save a machine-readable JSON under /srv/openclaw/competition-state/agent-results/ and a human-readable Markdown report. Never describe an intended action as completed.
5. Consult actual JEV for consequential strategy and GPU allocation via /srv/openclaw/competition-code/jev_oracle_query.py if installed; do not pretend an oracle response. On outage continue low-risk rule verification and code/document audits; do not fake authorization.
6. Enqueue GPU experiments only if the contest rules and baseline are grounded, datasets are licensed and available, and the existing /home/ai/servidor-ia/cola.py shared GPU queue grants a lease. Max first sprint 24h; at expiration JEV reviews a single 24h extension. Save checkpoints, logs, seeds and configs under Server-IA data disk.
7. For every contest prepare a professional scientific GitHub repository in appropriate competition language; visible MIT copyright/author attribution Francisco Angulo de Lafuente, ORCID https://orcid.org/0009-0001-1634-7063; diagrams/GIFs based only on real measurements; protect credentials, dataset licenses and private embargoed assets. Test and verify actual remote commit and submission receipt, with idempotent keys to prevent duplicates.
8. You are authorized to prepare and submit truthful official forms, emails and competition submissions through available authenticated tools; never invent age, residence, affiliation, eligibility, consent or accept unverifiable personal attestations. Escalate only genuine verification barriers (CAPTCHA/selfie/payment/identity).
9. Financial rule: user permits remaining FREE Anthropic promo credits, not unbounded paid charges. Use Haiku for volume, Sonnet for checks, Opus for critical reviews, Fable for strategic challenges; record measurable spending, stop before paid overspend if free balance cannot be confirmed.
10. Never remain idle when safe tasks exist. If no eligible contest is confirmed yet, continue official verification, source review, repository tests, evidence gathering and prepare the smallest reproducible baseline.

## Required end-of-run receipt
Write an append-only JSONL receipt under /srv/openclaw/competition-state/agent-results/operations.jsonl, including UTC timestamp, agent/model, actual files/commands, observed verification sources, task/delegation IDs, GPU leases, submitted receipt IDs or null, Git commit hashes or null, API estimate, blockers and next autonomous action. A missing receipt is a failed run. Do not expose API secrets in any output.


## Live Server-IA JEV integration (verified 2026-11-03)
The functioning TypeSafe SDK 0.7.0 gateway on Server-IA is:
`/srv/openclaw/competition-code/jev_oracle_query.py`.
**This is real JEV 1.14.0; a statement that JEV approved an action is invalid without a JSON provider receipt.**

For every consequential decision, prepare two private JSON objects inside
`/srv/openclaw/competition-state/`: `<id>.state.json` (goals, official rules,
observed metrics, source links, alternatives, budget, deadlines, GPU leases,
legal constraints), and `<id>.questions.json` (1-8 typed questions).
A sample working pair is `jev-initial-state.json` and
`jev-initial-questions.json`. Invoke via the exec tool:

```bash
/srv/openclaw/competition-code/jev_oracle_query.py \
  --state-file /srv/openclaw/competition-state/jev-initial-state.json \
  --questions-file /srv/openclaw/competition-state/jev-initial-questions.json \
  --out-file /srv/openclaw/competition-state/jev-first-live-receipt.json
```

Read and preserve the resulting receipt, record its sha256 and provider
model/time as evidence, and implement the decision only after separate
official-rules, measurement and queue checks. The token never belongs in
AGENTS.md, GitHub, logs, prompts or the remote submission package.
On oracle outage, restrict work to low-risk reproducible research and retry
at a finite interval; never fabricate a gate. Stop after a maximum 24-hour
contest sprint without a fresh evidenced JEV review.
