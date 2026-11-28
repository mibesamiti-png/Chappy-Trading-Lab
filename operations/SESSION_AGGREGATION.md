# Session-relative OHLCV aggregation building block

Engineering implementation of strict, non-overlapping 1/5/15/30 minute
aggregation from the existing research charter. Integer artificial OHLCV
fixtures only; this does NOT reproduce or reopen completed CTL-004 research.
The pure helper receives a single session's already normalized minute offsets
and explicit length, rejects duplicate/out-of-order/outside/invalid rows,
anchors windows to session start, rejects windows with missing bars and
discarded tails, and computes first open / max high / min low / last close /
sum volume. Never merges sessions. It has no file access or calendar
inference. No gap imputation. Future real-data adapter must establish
physical period isolation, normalized prices/types and exchange session
calendar separately. No new predictive branch or 2026 evaluation.

The automatic debug suite adds a fixed two-session fixture (one gap and
one short session) with known exact bar counts and 30-minute OHLCV values,
rejection cases and local deterministic receipt readback. Existing synthetic
checkpoint is unchanged; quality selection remains unchanged; reports
contain only status and timing. Does not authorize research execution.
