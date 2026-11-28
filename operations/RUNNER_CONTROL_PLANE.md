# Runner control plane — operational continuity

User reported v0.8.19 real one-candidate one-session aggregation PASS.
Main a2f16d770c0334a5165a62bf7695eee5adca3108 reports CTL-002–005
complete, CTL-001 blocked, CTL-006 approval_required, holdout locked.
No research branch reopened. The runner now reads the fixed public
queue and shared lease endpoints anonymously, validates the known scope,
skips completed research, and displays the next candidate. HTTP idle
is an observation only, NOT a CAS lease acquisition or proof of fresh
branch tip. Active or malformed lease stops, even if expired.
A local SQLite engineering ledger records a fingerprint of current
catalog/index/selection/calendar and prior successful validation
receipts and process launch identity. A different app process with
matching evidence can mark reopened. Same launch cannot pass; changed
evidence stops; no reset or overwrite on mismatch. Source metadata
is revalidated, market member bodies are not read. Prior receipts are
not identity-bound; do not claim verified same-member provenance.
Local transaction protects this ledger, not the shared scientific
RunGuard. This does not execute research, claim a remote lease, mark
CTL-001 complete, or demonstrate fresh-agent continuity. The actual
shared private research DB, original artifact registry, authenticated
CAS path and independent agent must still be qualified. No scheduling,
market values, private paths, or 2026 evaluation. Manual button only.
