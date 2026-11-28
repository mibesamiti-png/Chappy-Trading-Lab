# Candidate row-group logical period exclusion

The earlier research records describe bounded logical pre-2026 reads, but
the previous implementation is unavailable in the release branch. The
reported datetime/OHLCV schema is not independently verified here; the
candidate uses invented naive microsecond timestamps, float64 prices and
int64 volume, no inference of timezone or compatibility with real data.
Fixed generated Parquet only, no path arguments. Classify every group
using footer timestamp extrema and null-count evidence before reading
any projected data. Reject missing stats, overlaps, bad ordering, and
off-minute decoded timestamps. Read timestamps first for wholly pre-cutoff
groups, verify their extrema and monotonicity, then project OHLCV. Exclude
the entire crossing group (including its pre-cutoff portion), and all
reserved groups. No silent fill; coverage loss must be quantified before
scientific use. A single row group spanning the entire file would yield
no usable groups under this method. Metadata is not physical isolation;
ZIP decompression and Parquet footer may touch reserved bytes, and footer
statistics cannot establish truth for untrusted sources. Do not use this
prototype on registered archives. Actual reader policy, timestamp basis,
schema, independent calendar completeness and source validation remain
unresolved. Real research stays locked. No new prediction, 2026 evaluation,
or repeat of completed studies. Reuse existing PyArrow CI environment and
add a fixed 15th diagnostic. No market data or derived real results.
