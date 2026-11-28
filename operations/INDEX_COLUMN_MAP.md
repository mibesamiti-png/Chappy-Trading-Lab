# Existing index column mapping

Owner confirmed the real index schema-name probe succeeded. This release
reuses the saved local source reference and current ZIP metadata receipt.
Only fixed known table names are inspected with PRAGMA main.table_xinfo,
under a restrictive SQLite authorizer. No application-table SELECT, view
evaluation, row counts, default expressions or actual index row joins.
Candidate symbols are inferred from the observed filename suffix only;
duplicates and unknown formats are excluded and counted. The local report
shows possible join keys, not verified matching tickers or period boundaries.
Physical SQLite page isolation is not claimed. No real member reads,
2026 evaluation, publication of private outputs, or change of holdout status.
Actual column names and source correspondence require local evidence.
