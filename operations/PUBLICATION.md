# Public publication boundary

Only management status, methodological limitations and independently authored operational code/tests in the explicit allowlist are proposed here. No research measurements, source/derived datasets, per-symbol tables, aggregate effect estimates, restricted manifests, private paths or credentials are included.

`scripts/publication_gate.py` rejects unlisted files, traversal, symlinks, nontext/oversized files and several path/credential patterns. It does **not** determine ownership, data licensing or whether an arbitrary paragraph contains unapproved derived results. Full content and diff review is mandatory even after a mechanical pass; `.gitignore` alone is not a publication decision.

Before publishing:

1. Use an explicit list of intended text files. Never stage or upload a research output directory.
2. Review complete files and staged diff, including deleted lines, code fixtures and PR text.
3. Confirm each file is independently publishable; retain uncertain research material locally.
4. Reread main, claims and the shared lease; update only the dedicated branch with the expected head SHA, never force.
5. Read the resulting PR diff back from GitHub and verify main and the holdout state remain unchanged.

No provider-derived numerical findings are approved for public release by this operational review. A separate rights review is still required before publishing research artifacts. No software license has been selected.
