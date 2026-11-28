# Runner handoff receipt (v0.8.24)

Observed in GitHub: PR #43 comments 7236696520 and 7236706078 report
verified synthetic stage 1/2 and 2/2; shared lease last_claim_pr 43
released 2026-11-28T08:37:47.661084+00:00. Owner supplied local
v0.8.22 PASS report. No independent fresh AI session has run yet.
v0.8.23 main UI authentication reuse CI passed; real new-version
authentication has not been explicitly reported.

The existing research-control button now reads authenticated queue
and lease, verifies existing two-stage checkpoint chain and released
journals, reopens the same selected local SQLite guard in mode=ro,
and checks owner/status/deadline against stage 2. Check remote release
matches PR #43 and journal owner; reread remote and local state.
No acquisition, calculation, publication, checkpoint write or new DB.
Status is an observation, not a cross-store fence or fresh-agent proof.
No private paths, identities, tokens, market data or results in report.
If state changes, stop; do not repair or repeat a completed job.
Before dual pilot exists, preserve the prior local continuity flow.

## Fresh agent acceptance

In a new agent conversation, read current main, TASK_QUEUE.json,
HANDOFF.md, RESEARCH_CHARTER.md, operations/PERSISTENCE.md,
operations/LEASE_PROTOCOL.md and relevant open claims. Read shared
lease; never take over a foreign or expired active claim.
Review PR #41 and #43 as historical operational evidence. Ask owner
to run the existing research-control button in the installed runner
or use an explicitly authorized local execution surface; compare
the sanitized report. Do not rerun prior artificial or scientific
work. Independently qualify access to original private registry,
artifacts and same common DB if intended local surface allows.
Report exact category of remaining blockers. No new scientific
computation, market-member reads, 2026 evaluation or schedule.
CTL-001 remains blocked; CTL-002..005 completed per GitHub, CTL-006
approval required. No scientific or unattended readiness claim.
