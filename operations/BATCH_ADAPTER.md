# Logical batch adapter and bounded operational validation

Owner selected existing Parquet instead of redownloading CSV on 2026-11-28.
Observed one candidate: naive ns datetime, float64 OHLC, int64 Volume,
large_string source, single crossing group. Do not assume all members
have this schema. Exact schema gate, <=32 MiB member, <=2M rows, 8192
rows per batch, immutable in-memory ZIP member. No files extracted.
Full datetime-only pass validates strict global ordering and determines
pre-cutoff prefix. It internally decodes reserved timestamps; no reserved
counts or extrema leave worker. Second pass reads projected OHLCV only
through prefix, slices crossing batch before Python value conversion,
validates minute alignment, finite positive prices and nonnegative
volume, verifies timestamp prefix digest. Arrow may decode reserved
price pages internally; physical isolation is not asserted. Do not
assume the naive timestamp timezone from the file; use documented Eastern
basis and explicit calendar offsets only in the synthetic integration.
Float64 preserved without cents rounding, explicit float mode in existing
integer engine. Synthetic boundary fixtures include invalid reserved
prices, duplicate/disordered timestamps, empty prefix and invalid rows.
Real manual validation only consumes retained rows for input checks,
no scientific metrics, raw rows, paths, ticker names or counts output.
One current saved candidate, previous footer receipt required but not
identity-bound; do not assert same member. No automatic actual read.
One attempt marker, local cached enum receipt. No new research, no
2026 evaluation, no repeat of CTL-002–005. Actual research execution,
calendar completeness and independent continuity/lease remain gated.
