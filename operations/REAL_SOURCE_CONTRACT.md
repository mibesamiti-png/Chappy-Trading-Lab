# Local source contract and decision gate

Reviewed 2026-11-28. Academic descriptive research only. No new market
data retrieved, no market member or footer opened, no 2026 evaluation.

## Public documentation evidence (not local file verification)

- https://hfdatalibrary.com/pages/dictionary lists datetime (Eastern Time),
  float64 OHLC, int64 Volume, source string and additional Date/Time strings.
- https://huggingface.co/datasets/elkassabgi/hfdatalibrary lists the
  seven-column variant without Date/Time.
- https://hfdatalibrary.com/pages/ai-prompts describes naive Eastern
  timestamps but shows lower-case OHLCV names; do not infer the actual
  saved file schema or timestamp unit from these examples.
- https://hfdatalibrary.com/pages/api explicitly describes the full-history
  per-ticker endpoint with only a version parameter, no server-side date
  filtering. This is more specific than the landing-page range claim.
- https://hfdatalibrary.com/pages/docs documents IEX-only partial market
  observations, missing bars, non-point-in-time universe, split adjustment
  and a centered-window cleaning step. Keep descriptive-only limits.
- The earlier CTL-004 bounded logical read was reported in main STATE and
  execution records, but its private code and exact source metadata
  have not been recovered. Do not repeat the completed study.

## Next bounded acceptance, pending owner permission

One already selected registered member, maximum 32 MiB uncompressed,
read-only, memory only. Check identity against the current catalog and
selection. Explicitly disclose that the ZIP decompressor may process
the entire member including bytes from the reserved period and the
footer includes statistics for the full period. No data row decoding,
no price or volume values inspected, no date extrema or per-ticker
details returned to Chat or GitHub. A local report may contain schema
field names/types and only the classification counts of row groups
wholly before cutoff, crossing, reserved or unverified. If even that
metadata inspection is disallowed, use separately authorized pre-2026
artifacts only. No automated startup access.

Until explicit permission for that limited boundary exists, do not
implement an active real-archive reader or run a metadata probe.
No scientific execution is authorized by a successful probe.
Confirm exact datetime unit and timezone, float prices and integer
volume, optional extra columns, null handling and group sizes. Do not
silently round prices to cents; preserve numeric semantics. If a single
group spans both periods, the current exclusion candidate cannot
retain any of that group. Quantify coverage loss only under a
subsequently approved protocol. Preserve missingness, official calendar,
source vintage and pre-registered scope. CTL-001 fresh agent continuity,
local guard and remote lease remain separate gates.
