# Legacy handoff and continuity requirements
Revision 1 | 2026-11-27 JST
This document records historical decisions recalled from the prior research conversations. It is not a new test result, a license to use data, a trading strategy, or a change to the active academic queue. The underlying original records and test artifacts still need review.

## Historical project decisions to preserve
- R170 is the frozen integrated legacy comparison baseline. Preserve original source bytes, dependency pins, and acceptance evidence. Do not overwrite or retune it to fit new results. R171–173 data-management work was separated from the frozen baseline.
- Previous application development used simulated/virtual trading only; no real money or real order execution. Stable application versions and research experiments were kept separate. Historical principle: lack of adequate evidence for a viable edge means abstain, not relax thresholds or force a trade. Profitability was not established on genuinely unknown markets.
- Synthetic fixtures and observed market records must remain explicitly distinct. Never silently substitute artificial data for missing observations. Preserve provenance, declared observation times, missingness, costs and assumptions. Historical Japanese-market 5/15/30-minute experiments and data collection are separate from the present US IEX academic dataset.
- Existing research emphasized temporal causality, holdout isolation, leakage prevention, deterministic/reproducible comparisons, robust failure handling, and early termination of unproductive branches. Do not repeatedly optimize a frozen baseline or selectively report successes.
- Previous theoretical research was intended to develop hypotheses, seek counterexamples and revise conclusions, not merely accumulate models. Preserve rejected hypotheses with their conditions and reasons; do not assume a study filename establishes either success or failure.

## Separation and authorization
Current HF Data Library work is governed by RESEARCH_CHARTER.md and AUTONOMY_RULES.md: academic/educational only; no trading signals, real-trading algorithm development, live orders, or carrying restricted data, derived results or tailored artifacts into the historical legacy track unless explicitly permitted. 2026 academic holdout remains locked; legacy data boundaries are separate and cannot authorize opening it. Any future commercial track requires independent data rights, authorization and a fresh protocol. No brokerage integration or order execution is authorized.
Historical collection work must confirm source/storage rights, verify an end-to-end small sample before scaling, avoid exposing credentials, and preserve existing user files. Do not assume prior temporary-storage instructions authorize a new persistent copy. Existing user-managed archives remain read-only and must not be deleted.

## Outstanding recovery and acceptance
| Asset | Required evidence before claiming complete handoff |
|---|---|
| R170 integrated baseline | Full inspected source tree, original hashes/dependency closure, synthetic regression and prior acceptance record; unknown-market validation remains separate and unproven |
| Offline Lab and historical application releases | Recover exact versions, entrypoints, dependencies, documented simulation behavior and tests; do not mix stable/research implementations |
| Earlier experiments | Local round-to-source-to-test map, hypothesis/rejection ledger with original evidence and uncertainty, deduplication by content not name |
| R171–173 | Three sources archived in this PR; verify synthetic self-tests independently; fixed historic scope is not a generic importer |
| Work Phase 188–192 and later | Recover authorized local research artifacts; publish eligible generic code and synthetic fixtures only after review; independent scientific audit and cross-run persistence remain required |
| Shared operation | Verify fresh Work run can read current main and local artifacts, exclusive claim recovery, safe state updates and actual scheduler registration; do not claim automatic execution until confirmed |

Priorities: preserve the frozen baseline and original records first, then build a dependency map and reproduce synthetic tests. Import or re-execution must not interfere with active Work claims. This is continuity guidance, not authorization to start a new research branch or to publish underlying restricted artifacts.
