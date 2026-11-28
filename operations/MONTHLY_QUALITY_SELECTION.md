# Retrospective monthly index candidate selection

Owner supplied actual column names and confirmed 1253 unambiguous filename
candidates. No real data was accessed by this development session.
The local GUI explicitly requests a fixed SQL projection of identity-only
symbols columns and monthly_coverage rows whose month is one of the exact
46 YYYY-MM literals from 2022-03 through 2025-12. No whole-span statistics,
first/last dates, calendar or events are queried. Authorizer restricts columns;
it does not enforce predicates, so only the fixed built-in query is used.
SQLite may internally read mixed pages, and historical monthly aggregates
may reflect retrospective selection or source construction. Physical holdout
isolation and causal independence are NOT proven. No 2026 output/evaluation,
market member access, real research execution or predictive work authorized.

Exact ticker/filename, uncompressed size and eight-digit hex CRC match are
metadata consistency checks, NOT cryptographic payload verification. Unknown
CRC formats/members are excluded rather than guessed. Duplicate identities
and invalid/duplicate monthly rows cannot qualify. Weighted observed/scheduled
minutes from present valid months define an eligibility screen, not an
unbiased population coverage estimate. Default 12 months and 90% are
editable engineering demonstration settings, not a research protocol.
Deterministic seeded sample from eligible candidates is saved locally only.
Full unselected universe and reasons are summarized by counts; no trading
signals. Source size/mtime and catalog digest checked; not a security proof.
Original DB and archive remain unchanged. Actual DB formats, coverage and
match rates need owner-side validation.
