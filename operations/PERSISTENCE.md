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

1. Review/merge operational changes through the maintainer; do not write main directly.
2. Select the intended local execution surface and confirm its private registry and tool access from an actual fresh agent run.
3. Confirm access to existing artifacts and checkpoints without rescanning market data. Publish only pass/fail/unverified status.
4. Acquire the repository-wide lease and local guard before any computation; skip completed task/revision identifiers. Follow `LEASE_PROTOCOL.md`.
5. Use a bounded per-invocation budget and safe checkpoints; do not infer allowance resets from the interval.
6. Only after the persistence probe and owner scheduling decision, create scheduling through the native automation action. A true five-hour interval must continue across day boundaries; a set of five wall-clock hours per day is not equivalent.
7. Inspect early real runs for delayed triggers, missed access, overlap and checkpoint recovery. Do not call a schedule reliable before those observations exist.

Official documentation states local-file tasks need the computer on and desktop app running; web tasks cannot directly work in a local folder. This is a prerequisite, not evidence that this particular installation has passed an overnight/restart test. See [Scheduled tasks](https://learn.chatgpt.com/docs/automations?surface=app).

No cloud execution, uploaded dataset, wake-from-sleep capability or schedule activation is claimed.
