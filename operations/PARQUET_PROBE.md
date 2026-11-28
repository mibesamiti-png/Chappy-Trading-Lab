# Dedicated Parquet environment (synthetic only)

The owner chooses install/test, test only, or cancel before execution.
The GUI runs a fixed worker off the UI thread; update application is deferred
while busy. It uses a version-specific local venv with an ownership marker,
official PyPI binary wheels only, PyArrow 26.0.1 pinned, no source build,
no inherited GitHub credentials or custom pip index. Installation can be
retried in the same owned directory; no deletion or global package changes.
Timeouts are per subprocess. No live process cancellation is implemented.
Closing during installation may leave the non-daemon worker finishing its
bounded operation. Detailed subprocess output is not exposed or published.

The worker generates a small artificial Parquet member with a forced ZIP64
local header, reads only that member, rejects a mixed 2025/2026 fixture,
and stores/reopens a synthetic receipt. This is not proof of large ZIP64
central-directory handling or mixed-year real-market safety. Registered
market ZIPs are never opened. A verified development-only source boundary
and explicit next gate are still required. No live trading or scheduling.
