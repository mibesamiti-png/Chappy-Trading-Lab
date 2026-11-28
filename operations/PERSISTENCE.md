# Persistence and recurring-run readiness

Status: preparation verified locally; actual scheduled-agent continuity is **unverified**. No schedule was created or activated.

## Evidence collected

- Existing local input references, prior indexes and reports were reopened from a fresh isolated Python interpreter.
- A persisted task checkpoint was reread by that separate process.
- An active writer excluded another process. Simultaneous synthetic contenders produced exactly one winner.
- Foreign-owner writes and releases were rejected; expiry never silently transferred ownership.
- Completed task/revision identifiers persisted across owners and are idempotent.
- A real GitHub lease update with an outdated file SHA was rejected with HTTP 409, and the active owner remained unchanged.

These checks do not simulate a new agent conversation, application restart, machine sleep, a delayed trigger, future tool permissions, dependency access under unattended execution, or a five-hour interval. CTL-001 stays blocked on that acceptance gap.

An additional dependency probe failed to import the full research stack in the ordinary constrained execution context, while the approved computation context imported it successfully. Existing-file readability is therefore insufficient evidence of unattended research readiness. Qualify the intended agent's dependency access and execution permissions before enabling any periodic computation; no machine-wide permission changes were made.

## Private artifact registry

The candidate local checkout has an ignored `.local/registry.json` containing references to the existing private workspace, inputs, dependencies and checkpoints. It does not copy the dataset. Exact paths and manifests must never enter GitHub. A fresh clone/worktree will not contain this ignored registry; stop if it cannot be resolved through an already authorized private handoff. Chat reads public coordination status, not these local artifacts.

## Before enabling an approximately five-hour cadence

1. Operational changes were merged with owner approval at `a2f16d770c0334a5165a62bf7695eee5adca3108`; use current main. Chat independently reproduced 10/10 original operational tests at PR #1 head. This does not establish combined-main CI or fresh-agent access.
2. Select the intended local execution surface and perform the bounded fresh manual Work probe in [HANDOFF](../HANDOFF.md). Confirm existing registry, checkpoint, required dependency imports and permissions; do not recreate missing inputs or read protected observations.
3. Confirm access to existing artifacts and checkpoints without rescanning market data. Publish only pass/fail/unverified status.
4. Acquire the repository-wide lease and local guard before any computation; skip completed task/revision identifiers. Follow `LEASE_PROTOCOL.md`.
5. Use a bounded per-invocation budget and safe checkpoints; do not infer allowance resets from the interval.
6. Only after the manual persistence probe passes and the owner makes a separate scheduling decision, use the native automation action for a bounded unattended environment probe before enabling research. A manual pass is not unattended readiness. A true five-hour interval must continue across day boundaries; a set of five wall-clock hours per day is not equivalent.
7. Inspect early real runs for delayed triggers, missed access, overlap and checkpoint recovery. Do not call a schedule reliable before those observations exist.

Official documentation states local-file tasks need the computer on and desktop app running; web tasks cannot directly work in a local folder. This is a prerequisite, not evidence that this particular installation has passed an overnight/restart test. See [Scheduled tasks](https://learn.chatgpt.com/docs/automations?surface=app).

No cloud execution, uploaded dataset, wake-from-sleep capability or schedule activation is claimed.

## 2026-11-28 runner acceptance and remaining boundary

Release branch `chat/runner-source-releases-20261128`, v0.8.24 signed
merge `281eddccb8fd468a96812eb25165a089fa10763f` (PR #46). Owner
reported a successful v0.8.24 read-only handoff on 2026-11-28 JST:
saved artificial stages 2/2, main-screen authentication, selected
local DB identity and release metadata, matching shared lease release.
Chat independently observed GitHub PR #41 operational report and PR
#43 stage comments 7236696520 and 7236706078, and the idle lease with
last_claim_pr 43. Runner restart and two-stage artificial resume were
owner-tested; the scientific checkpoint itself was not inspected.
PR #46 Windows/Linux 108 tests each passed, with mocked CAS transport.

These are runner engineering milestones, not proof that a new AI has
access to the original Work private registry and scientific artifacts,
or proof that the selected runner DB is the same DB used by Work.
PR #5's separate Work access failure remains historical evidence;
PR #6's original-context access and dependency failure remain distinct.
CTL-001 is blocked pending actual fresh-agent acceptance; CTL-002–005
remain completed per prior record; CTL-006 and 2026 remain locked.
No scheduled execution, new research, or predictive scope expansion.
