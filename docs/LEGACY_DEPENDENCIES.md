# Legacy dependency map and reuse guide
Revision 1 | 2026-11-27 JST. Based on inspected source headers and explicit run_path/import references, not on filenames alone. This is partial and does not certify a runnable dependency closure.

## Frozen integrated lineage
```
R170 integrated package (archive located; contents not yet inspected)
  R169 Integrated Lab (separate source inspected; package membership unverified)
    R168 Data Safety Adapter [hash-pinned]
      R166 Capital Lifecycle Study [hash-pinned]
        R165 Capital Aware Learning [hash-pinned]
          R162 Multi Horizon Learning Study [hash-pinned]
        R153 Configured Lifecycle Study [hash-pinned]
```
R164 Capital Diagnostic is a separate diagnostic depending on R163 Multi Horizon CTRL Evaluation and saved R163 results; it is not assumed to be part of the R170 runtime. Its dependencies include historical data artifacts and must remain local until rights are known. Further transitive dependencies are not yet resolved. Do not take the separately located R169 entrypoint as proof of R170 package identity. Preserve archive and exact source hashes; never edit the frozen baseline just to make dependencies pass.

## Earlier sampled lineage
```
R86 Statistical Gate -> R85 Random Market -> R84 Latency Phase
R99 Selective Hypothesis -> R98 Observation Imbalance
```
Source code explicitly pins each parent; remaining graph and results unreviewed.

## Recovered data-management lineage
```
R172 Market Data Provider -> R171 Collector
R173 Market Data Import -> R171 Collector (SHA-256 pinned)
```
These are source-only snapshots under legacy/r171_r173. R171 synthetic storage, R172 synthetic provider contract, R173 authorized offline CSV import. Fixed historic Japanese-market scope; not compatible with HF data as-is, and do not wire them into that research. Use synthetic-only self-tests locally in a clean environment first. The prior reported tests and limitations are summarized in LEGACY_EVIDENCE.md.

## Work reuse policy
- Read LEGACY_HANDOFF.md, LEGACY_INTAKE.md, LEGACY_EVIDENCE.md and this map before proposing duplicate historical experiments.
- For academic HF research, reuse only rights-cleared, domain-general techniques such as input validation, synthetic controls, provenance tracking and audit design. Do not use HF data to develop real-trading algorithms or link restricted results to legacy simulations.
- Historical algorithms, configurations, exact candidate choices and data-dependent results belong to the separate legacy track; no automatic integration or adaptation.
- Any task that needs an unavailable dependency must record it as blocked rather than replace it with an invented implementation. Record original source hash, exact version, parent edges and test scope when recovering additional artifacts.
- Public GitHub is not backup storage for restricted assets. Keep the original archives and results locally and preserve the 2026 academic holdout.

## Missing assets and ownership
The R170 and Offline Lab ZIPs, other application ZIPs and ZIP Splitter are located by metadata but cannot yet be unpacked by Chat. Work owns current Phase 188+ local files. Request source-only recovery and synthetic regression through a separate authorized task after current research checkpoint; do not overlap existing claims.
