# Cooperative single-writer protocol

All cooperating runs use the **same** `coordination/lease` branch and `coordination/lease.json` file. A lease on each research branch is insufficient. This coordination branch contains operational state only and is separate from main.

1. Read current main, open issues/PRs, and the shared lease. Stop for another active claim, an ambiguous owner, a missing/invalid lease, or unavailable repository access.
2. Maintain a dedicated research branch and draft PR with tasks and a bounded budget. Claim before computation.
3. Acquire an idle lease by updating the file with its current GitHub blob SHA. A stale SHA must fail; reread instead of retrying blindly. Record a non-secret unique owner, claim PR, task IDs and UTC deadline.
4. Acquire `RunGuard` on the common private state database. This database must be shared across local checkouts for this research project, not recreated inside every isolated worktree.
5. Before a unit of work and before publication, confirm both owner/deadline guards and current queue dependencies. Check completed task/protocol-revision identifiers and resume checkpoints rather than repeating completed research.
6. On limits or loss of ownership, stop computation and preserve a private checkpoint. Do not create a replacement schedule or bypass limits.
7. Publish sanitized checkpoint status through the claimed draft PR. Release only the lease owned by this invocation using the current SHA. Persist task completion only after its evidence has been saved.

Expiry is a stop signal for its writer, **not** permission for a contender to steal the lease. A stale/abandoned lease needs verification that its previous writer stopped and explicit reconciliation; no automatic expiry takeover is implemented. A local owner mismatch also fails closed.

The local guard uses SQLite write transactions and persistent ownership/completion records. The remote coordination check uses GitHub contents-SHA compare-and-swap. The real stale-update test failed with HTTP 409 as expected; synthetic local contention/restart tests passed.

This is a cooperative protocol, not server-enforced atomic fencing across multiple GitHub refs. It cannot protect against a writer ignoring these rules, unverified expiry takeover, or an unattended scheduler that never calls the guard. Actual scheduled-agent integration remains unverified. No scheduled research should be enabled until that path has been tested.
