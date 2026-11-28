# Local candidate selection and artificial OHLCV audit

The owner confirmed 1253 catalog entries and 1253 Parquet candidates in the
registered real ZIP, with zero member reads. The selection GUI reads only the
local catalog, checks registered paths and size/mtime freshness, searches file
names (not proven ticker identifiers), and saves at most 128 selected entries.
No real member access is implemented. Catalog digest and selection receipt are
local; neither is independent proof of time coverage. Do not publish them.

An isolated fixed artificial Parquet worker checks duplicates, backward time,
same-UTC-day minute gaps, off-minute timestamps, nulls, invalid integer OHLCV
and a mixed-period refusal; no market/session calendar or real schema asserted.
Reports elapsed time and Arrow bytes allocated at end (not peak process memory).
The worker uses the installed dedicated PyArrow environment and saves a synthetic
receipt. An independently verified development-only data boundary is required
before opening real members. Holdout remains locked; no new research execution
or predictive model development authorized.
