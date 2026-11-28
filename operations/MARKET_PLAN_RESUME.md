# Durable metadata preparation plan

The local plan freezes catalog digest, selection mode, batch size, seed,
algorithm and rationale. A persisted cursor tracks prepared candidate counts,
not research execution. Each explicit next-batch action saves the deterministic
candidate receipt before advancing the plan. Interruption before cursor commit
replays the same receipt. Existing plans are never silently overwritten.
Opening a plan checks current catalog freshness and cursor consistency.
No automatic scheduling, actual payload execution, cross-process lease,
or independent period proof is introduced. This is a single-GUI preparation
checkpoint; concurrent independent processes are not supported.
The latest batch receipt is overwritten by later batches and is not a result
ledger. All real market data remains locked. No new research hypotheses.
