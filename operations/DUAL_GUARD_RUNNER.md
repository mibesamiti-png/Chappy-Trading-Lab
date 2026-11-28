# Dual guard operational pilot (v0.8.21)

User-reported v0.8.20 separate launch continuity PASS. Dedicated draft
PR #41, one manual operational acceptance, no science. Use authenticated
GitHub CLI if installed or transient masked token input; never read vault
or store/log credentials. Fixed HTTPS endpoints, reject redirects on
token path. Requires contents read/write and PR comment permission.
Select existing run_guard.sqlite, validate layout, no replacement DB.
Shared DB identity with Work remains unverified. Read queue, open PRs,
claim PR and live lease blob SHA; refuse active or expired claims.
CAS claim before local BEGIN IMMEDIATE. Preserve old checkpoint and
completed records. Persist separate journal, check owners and deadline,
post fixed safe status, release local then remote using current SHA.
Ambiguous write or interrupted attempt stops for reconciliation; no
automatic takeover or retry. Successful receipt reusable. No research,
market member read, 2026 evaluation, or schedule. Does not mark CTL-001
complete or demonstrate actual fresh AI session continuity.
CI uses invented DB and mock CAS; actual authenticated PC pilot pending.
