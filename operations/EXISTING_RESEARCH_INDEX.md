# Existing research index intake (schema only)

The earlier research handoff reports a lightweight SQLite index and saved
private CTL-002–005 artifacts. Their original local location and actual
schema are not accessible to this Chat session. The owner can select the
existing hf_light_index.sqlite in the research settings UI. This checks
only SQLite schema object names/types via a read-only immutable connection
and a restrictive authorizer. No application-table SQL, row counts,
timestamp ranges, market member reads or 2026 evaluation. SQLite may
internally read database pages to resolve schema; the claim is logical
schema-only access, not a physical byte-level isolation guarantee.
Reject sidecar WAL/journal/SHM, nonregular/reparse files, wrong names,
oversized sources, changed metadata and unsupported schema objects.
Save a local receipt; do not publish it. It establishes local schema
access only, not a development-only partition, genuine fresh-agent
acceptance, or permission to conduct new research. The source is never
modified; an independently established development-only boundary remains
required. No new study, scheduling or predictive escalation.
