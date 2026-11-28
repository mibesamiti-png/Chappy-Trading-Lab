# Shared authentication (v0.8.23)

Owner supplied the installed desktop.py; SHA-256 matches the pinned
desktop.py in v0.8.22 exactly. Desktop.get_token() uses the current
masked field, validates using existing api_bridge, and delegates
optional retention to the existing DPAPI vault. The runner now calls
this API from the GUI thread and passes a transient token snapshot to
the existing fixed-endpoint HTTPS transport. No additional dialog,
CLI fallback, vault read, stored token copy, token report or new
credential mechanism. The original desktop/vault/bridge bytes are
unchanged. Refuse overlapping mailbox busy/resident operation; use
base busy state during the guarded worker. When prior artificial
2/2 completion is saved, the existing button performs only a
read-only authenticated queue/lease check; never reclaims or reruns.
Read-only authentication does not prove current write permission.
No market reads, research execution, holdout access or schedule.
Owner reported real v0.8.22 resume PASS; both stage comments and
idle release observed independently. New auth UI real-PC test pending.
