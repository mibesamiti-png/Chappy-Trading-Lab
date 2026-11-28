# Two-minute GUI update probe

Owner requested about two-minute auto-update checks, immediate manual
communication, and evidence instead of an unsupported "latest" label.
Original launcher.pyw is not present in this release repository. The GUI
therefore performs an independent anonymous HTTPS read of the fixed public
release manifest at startup, then every 120 seconds while enabled, and on
manual click. No token, no private inputs, no arbitrary endpoint. A bounded
response and closed manifest schema are validated, version comparison is
numeric, failures and older responses are explicitly unverified. HTTP status,
local and response versions, elapsed time and outcome are logged; the current
probe snapshot is appended to the copied diagnostic report if available.

This is informational manifest retrieval, NOT GitHub commit-signature or
branch-tip freshness verification. Cache-control and a unique query parameter
are used; a same-version response is not proof of current branch tip.
Only a newer observed version requests the existing supervisor via its
check-now marker. Signature validation, download, safe replacement and
restart remain the existing supervisor's responsibility. Its polling time,
actual apply latency, existing log wording and internal ten-minute timer
are unchanged; actual manual check and GUI timer need real PC validation.
No duplicate probe in flight; existing pending marker is not overwritten.
No scientific research, data reads or new scheduling authorization.
