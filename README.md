# Chappy-Trading-Lab

Autonomous quantitative market research and statistical analysis framework.

## Purpose

Research reproducible statistical properties of markets under explicit data licensing and scientific validation constraints. This public repository is a coordination layer for Chat and Work, not a data store. Current HF Data Library studies are for academic/educational use only; no trading signals or live trading system development using restricted data.

## Start here

- [ROADMAP.md](ROADMAP.md) — gates and acceptance criteria.
- [RESEARCH_CHARTER.md](RESEARCH_CHARTER.md) — detailed questions, evidence and identification limits.
- [STATE.md](STATE.md) — latest reported status and limitations.
- [TASK_QUEUE.json](TASK_QUEUE.json) — prioritized research work.
- [AUTONOMY_RULES.md](AUTONOMY_RULES.md) — execution, safety, publication and stop rules.
- [HANDOFF.md](HANDOFF.md) — next run and artifact access requirements.

Work performs computation in its authorized environment. Chat coordinates and reviews published, sanitized records. The 2026 final holdout remains locked until a frozen protocol and explicit approval. The intended cadence is approximately five hours, not yet activated or verified.

## Public boundary

Do not upload source datasets, split archives, private manifests, unapproved derived results, model artifacts, credentials, or personal paths. The repository's public visibility does not license third-party data. Inspect all files and diffs before pushing; ignore rules alone are not sufficient.

No financial performance is claimed. No software license is selected yet.

## Latest proposed operational handoff

[Draft PR #1](https://github.com/mibesamiti-png/Chappy-Trading-Lab/pull/1) records the bounded local persistence/audit/robustness run. Until maintainer review, read its proposed STATE, TASK_QUEUE and HANDOFF alongside main. No schedule activation or independent Chat verification is claimed.

- [Persistence evidence and unverified scheduler boundary](operations/PERSISTENCE.md)
- [Shared lease and completed-task protocol](operations/LEASE_PROTOCOL.md)
- [Public file/content review boundary](operations/PUBLICATION.md)
