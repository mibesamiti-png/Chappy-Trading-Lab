# One-member local metadata probe

Owner approved the previously proposed one-member metadata-only inspection
on 2026-11-28. Scope: one saved candidate, <=32 MiB uncompressed, memory
only, no row decoding or scientific evaluation. No change to holdout
or scientific access lock. Manual button only, never automatic startup.
Choose first saved candidate within cap, verify current metadata admission,
selected identity, ZIP entry CRC/size, and current catalog before/after.
A local exclusive attempt marker prevents automatic repeat even on
failure; a completed receipt can be copied again without touching ZIP.
Schema names and types use a fixed safe vocabulary (unknowns redacted),
group counts only, no exact date extrema, prices, paths, ticker names,
or private market data in GitHub. Full compressed member is expanded in
memory; footer metadata may include reserved-period bytes and statistics.
Physical isolation remains unverified. No data pages decoded by the
metadata worker. Counts based on timestamp metadata, not validated rows;
naive timestamps use provider-documented Eastern basis, UTC cutoff
conservative. Unknown type/zone/statistics classified unverified.
No repeat of completed studies and no research unlock. Existing diagnostic
receipt counts apply to that automatic diagnostic, not lifetime access.
Tests use generated fixtures only. User PC execution remains pending.
