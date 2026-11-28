# Reproducible automatic candidate selection

Metadata only: select from the validated local catalog using deterministic
SHA-256 ranking of seed + archive/member identity, or sorted sequential
batches. All batches of one frozen catalog and fixed policy partition the
candidate universe without repetition. Seed, algorithm, batch size/index,
next batch and selection rationale are saved locally along with the catalog
digest. Manual selection is preserved separately. This is not a durable
execution cursor; changing the policy or catalog starts a different plan.
The user triggers each batch; there is no scheduled job or AI planning yet.
Do not infer actual data quality, industry, liquidity or eligibility from
filenames. Research access remains LOCKED, no payload reads, no trade signals.
