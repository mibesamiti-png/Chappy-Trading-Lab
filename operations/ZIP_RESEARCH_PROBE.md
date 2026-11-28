# ZIP research pipeline probe

Scope: synthetic only. The new local GUI test generates an invented ZIP in memory,
checks a bounded catalog, reads one fixed member, parses invented dated values,
rejects dates in 2026 or later, verifies a known result, and writes/reopens a
synthetic receipt. No registered input is opened, and nothing is posted.

The small limits are deliberately for this artificial probe, not production archive
limits. The registered market archive may be much larger, may require ZIP64 and
may contain mixed years within a single Parquet member. The synthetic date check
is not a real holdout access guard: do not open a real member to discover whether
it contains 2026. A separately verified development-only source boundary and
owner-approved research scope are required before any real input read.

PyArrow detection in the GUI is presence only, not an import or Parquet test.
Next gate: validate an invented Parquet archive, a production-sized central
directory approach, dependency availability, and a trusted period partition
without opening reserved observations. Existing CTL-001 lease and restart
requirements remain; no scheduled or live-trading execution.
