# Descriptive statistics building block

Pure helper using the existing strict session-relative OHLCV aggregation.
Each supplied session is independent. Close-to-close simple fractional
returns use only adjacent complete bars within that session; no crossing
missing windows or overnight boundaries. For each of 1/5/15/30 minutes,
counts of complete/missing windows, tail minutes, possible/observed/missing
adjacent pairs, positive/negative/zero moves, arithmetic mean return, mean
absolute return, sample SD (n-1), volume sum and mean are defined.
Equal weight per observed bar/pair, not per session. Empty estimates are
None, not zero; sample SD requires two returns. Values are invented integer
prices; real price scale and calendar coverage not established. This is
descriptive only, no hypothesis testing, independence assumption,
annualization, prediction, profitability or live trading. It does not
reopen completed CTL-004/005. A fixed synthetic known-effect fixture and
flat-price four-horizon fixture check exact counts, values, empty
estimates and receipt reproducibility. Twelfth auto diagnostic records
only status/time. No market member access, 2026 evaluation or permission
to execute real research. Source adapter and approved research scope
remain separate gates.
