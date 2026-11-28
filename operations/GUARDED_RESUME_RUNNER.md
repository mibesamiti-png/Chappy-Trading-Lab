# Guarded resume runner v0.8.22

Owner-reported v0.8.21 and independently observed PR #41 comment and
idle lease release. New fixed synthetic job claimed via draft PR #43.
Reuse both guards, current queue validation and authenticated CAS.
Each manual invocation performs one stage under both guards and saves
a private checkpoint, publishes fixed sanitized status, releases both.
Stage 1: invented 30-minute series, 5-minute bars with one missing window.
Stage 2: adjacent bar changes computed from saved stage 1 bars only.
Stage 1 is not rerun; stage 2 requires verified stage 1 release journal.
Record the chosen DB path and file identity locally; second stage
reuses it and rejects mismatch. No credentials stored. Stop on missing,
incomplete or altered evidence; no automatic takeover. Existing
scientific checkpoint and completed table are untouched. Fixed two
stages; no market member reads, 2026 evaluation, scientific execution,
schedule or fresh AI session continuity claim. CI mock CAS only.
