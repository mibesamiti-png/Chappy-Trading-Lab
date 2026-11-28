# Explicit session mapping

A pure adapter from UTC epoch-minute integer OHLCV to the existing
session-relative aggregation helper. Input schedule supplies each session's
date, UTC offset (-300/-240 minutes), and duration (1..390 minutes); open is
09:30 local. Strict half-open boundaries, ordered unique valid rows, explicit
outside-session counts and 2000..2025 guard. Dates absent from the supplied
schedule are outside-session, not inferred official holidays. No timezone
database dependency or inferred DST dates. No actual calendar reader or
market ZIP access. The adapter does not certify the supplied calendar,
prove timestamp labeling or physical holdout isolation. Fixed invented
winter/summer/short/closed-day cases and exact integration with 30-minute
bars are checked by the ninth automatic diagnostic. Local synthetic receipt
only. No reopening CTL-004, new predictive research or 2026 evaluation.
