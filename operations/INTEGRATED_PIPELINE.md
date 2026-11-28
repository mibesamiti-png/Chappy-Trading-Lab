# Synthetic integrated pipeline

Reuses the installed isolated PyArrow environment and existing session
mapping, OHLCV aggregation and descriptive statistics. Fixed generated ZIP
with a compressed Parquet member and unrelated invalid member. The fixed
worker reads only the invented selected member, validates typed UTC
timestamps and rejects an invented 2026 row; no inputs from registered
market data. The parent maps two invented sessions (winter/summer offsets),
one missing minute, four outside rows, different constant prices across
sessions; verifies exact counts and no spurious cross-session/gap returns
at all four horizons. Empty adjacent-pair estimates remain null.
Deterministic local receipt and thirteenth automatic diagnostic; reuse the
existing actual PyArrow CI installation test for end-to-end execution twice.
No real archive access, physical period isolation proof, scientific
protocol, completed research rerun or predictive work. The input schema
is synthetic, not proof of compatibility with actual market member data.
