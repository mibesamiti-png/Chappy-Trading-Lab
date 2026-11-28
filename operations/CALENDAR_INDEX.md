# Existing calendar index adapter

Fixed local read-only projection of five ordinary calendar columns: date,
expected_minutes, open_utc, close_utc, utc_offset_hours. Date predicate
2022-03-07 through 2025-12-31, bounded row count and strict date validation.
No observed_tickers, observed rows, market member data or 2026 results.
Authorizer limits columns, not predicates; only fixed built-in SQL runs.
SQLite may internally read mixed pages. Physical isolation is unverified.
Uses existing validated local index map and checks file attributes before
and after. Normalizes explicit UTC clocks or same-date timestamps with
minute alignment and offset -5/-4, cross-checks 09:30 local open and duration,
rejects unknown representations, duplicates and inconsistent clocks.
Closed rows require empty/null clocks. No inferred missing holidays, official
calendar verification or completeness certification. Saved local calendar
receipt is metadata, not research authorization. Two automatic checks:
invented in-memory SQL fixture (reserved row excluded and unrelated column
denied) with mapping integration, and registered local index check if
configured. No upload, private details or scientific computation.
