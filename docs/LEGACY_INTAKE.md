# Legacy research intake (2026-11-27 JST)
This is an inventory, not a validation certificate. Historical pre-HF source stays isolated from the academic HF-data study. No restricted data, local paths, credentials, provider-derived records, or past result datasets are included. No license is granted by this document.

## Imported first batch (R171–173)
Three complete ASCII source texts recovered from the user's library, terminal LF restored to match listed byte sizes, and read back from GitHub. R171 SHA-256 matches the dependency pin in R173. R172 and R173 hashes below describe the recovered text; no independent original hashes available. No new runtime tests performed due to unavailable execution environment. Keep these as historical snapshots, not production-ready code.
- R171 Collector: synthetic only, exact-price conversion, atomic ingest, conflict rejection, receipt checks and provenance inventory.
- R172 Provider: synthetic contract only, bounded retries, identity verification, raw synthetic payload auditing; no real network client.
- R173 Import: offline authorized CSV path, explicit permission and metadata, separate database from synthetic, no network or automatic market collection. Fixed Japanese calendar and symbols; not a generic US-market/HF data importer.

| Source | Recovered SHA-256 |
|---|---|
| Collector | 184f3674d28f15cbc9c2c289bf844bc12907eefcafb37f0fb284ae110129a67f |
| Provider | f6cebc0a63e0ccd6d36f94bbcf6d6952e8008a819cb73598e59eb53fcf896396 |
| Import | f4fb7c654b85a9edaecb8577fef513b87ea2ed1fe075df8964a2e86e646ba |

All three are in `legacy/r171_r173/`. For a separate synthetic-only regression, run each with Python 3 and `--self-test --output <fresh-local-path>.json`. Do not publish generated results without review. Do not connect these to restricted HF data.

## Recovery priorities
1. Recover and inspect R170 integrated ZIP and Offline Lab ZIP, retaining dependency pins and directory layout; do not republish archives directly. Review each source file and fixture before extraction/import. Exclude third-party records, previous result data and credentials. Runtime tests on synthetic fixtures are required before reuse.
2. Review the older individual studies and prior test reports for already attempted questions, dependencies and negative results; create a local evidence-linked index. Publication requires explicit permission/rights review. Historical research findings must not be inferred from file names.
3. ZIP splitter: inspect original archive contents before source-only import; preserve original tool behavior and document the temporary resume script separately. No user manifest or market ZIPs in GitHub.
4. Work Phase 188–192: Work owns local artifacts and is responsible for separately reviewed publication of eligible generic source and synthetic tests. Never import local raw/restricted data, unapproved derived outputs, or existing restricted-data models. No scope or claim changes to Work PR #1.
5. Check older application versions and any additional archives not listed here. Do not merge an incomplete legacy snapshot into the current research implementation. Keep historical R170 and HF academic track separate.
6. Add source-only synthetic CI once dependencies and rights are verified, with no data download or brokerage integration.

## Library inventory (filename metadata only)
233 distinct matching filenames observed in 12 pages of native library metadata (duplicates by identical name grouped, version suffixes kept). Listing was bounded and additional pages may exist. Recursive Google Drive enumeration was not supported; this does not cover local PC or Work. No claim about the contents of unreviewed archives.

| Filename | Intake status |
|---|---|
| `Chappy_Market_Data_Collector_v0.1.py` | Imported; text readback verified |
| `Chappy_Market_Data_Import_v0.1.py` | Imported; text readback verified |
| `Chappy_Market_Data_Provider_v0.1.py` | Imported; text readback verified |
| `Chappy_Trading_Acceptance_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Allocation_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Depth_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Drift_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Evidence_Ledger_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Integration_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Ledger_Integration_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Monitor_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Admission_Recovery_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Adoption_Gate_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Alarm_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Applicability_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Archive_Race_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Audit_Value_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Baseline_Audit_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Baseline_Audit_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Beta_Audit_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Bounded_Receipt_Gate_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_CSV_Input_Guard_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_CTRL_Evaluation_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_CTRL_Intake_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Calibration_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Candidate_Limit_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Candidate_Selection_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Capital_Aware_Learning_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Capital_Comparison_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Capital_Diagnostic_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Capital_Lifecycle_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Common_Document_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Comparison_Drift_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Composite_Hypothesis_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Conditional_Edge_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Conditional_Hypothesis_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Configured_Lifecycle_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Consensus_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Consensus_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Admission_Comparison_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Admission_Comparison_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Comparison_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Cost_Comparison_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Diagnostic_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Evidence_Diagnostic_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Core_Pause_Comparison_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Coverage_Monitor_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Cross_Sector_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Daily_Event_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Daily_Event_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Data_Recovery_Gate_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Data_Safety_Adapter_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Decision_Journal_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Decision_Quality_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Decision_Quality_v0.2.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Decision_Review_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Decision_Review_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Delayed_Coverage_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Dependency_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Diagnostic_Monitor_v0.2.zip` | Located by filename; full source review/import pending |
| `Chappy_Trading_Diagnostic_Response_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Document_Integration_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Document_Monitor_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Document_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Dual_Monitor_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Durability_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Durability_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Durable_Replay_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Economic_Monitor_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Economic_Value_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Eligible_Evidence_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Eligible_Lifecycle_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Estimation_Comparison_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_Bundle_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_NextDay_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_Policy_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_Policy_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_Replay_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Event_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Dependency_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Gate_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Gate_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Journal_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Journal_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Lifetime_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Paper_Bridge_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Paper_Bridge_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Evidence_Sensitivity_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Expected_Value_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Expected_Value_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_External_Audit_Ledger_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Feature_Interaction_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_FeedSafety_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_FeedSafety_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Foundation_Audit_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Foundation_Audit_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_History_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_History_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Hypothesis_Capacity_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Hypothesis_Generation_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Hypothesis_Penalty_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Hypothesis_Pool_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Improvement_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Ingest_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Calibration_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Hypothesis_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Improvement_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Lab_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Lab_v0.1_R170.zip` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Monitor_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Refresh_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Replay_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Replay_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integrated_Review_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integration_Audit_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Integration_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Knowledge_Archive_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Knowledge_Refresh_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Known_Market_Diagnostic_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.2.0(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.2.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.3.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.4.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.5.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.6.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.7.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.8.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v0.9.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.0.0-rc1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.0.0-rc2.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.0.0-rc3.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.0.0-rc4.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.0.0-rc5.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.0.0-rc6.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha2.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha3(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha3.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha4(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha4.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha5(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-alpha5.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lab_v1.1.0-rc1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Latency_Phase_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Latency_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Latency_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lifecycle_Audit_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Lifecycle_Priority_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_LongShort_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_LongShort_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Market_Context_Adapter_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Market_Context_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Market_Replay_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Market_Replay_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Mature_Evidence_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Monitor_Evidence_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Monitor_v0.1.zip` | Located by filename; full source review/import pending |
| `Chappy_Trading_Multi_Horizon_Adapter_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Multi_Horizon_CTRL_Evaluation_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Multi_Horizon_Learning_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Multi_Monitor_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_OHLCV_Capital_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_OHLCV_Capital_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_OHLCV_Input_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_OHLCV_Refresh_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Observation_Coverage_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Observation_Identity_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Observation_Imbalance_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Offline_Evaluation_CLI_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Offline_Lab_v0.1.zip` | Located by filename; full source review/import pending |
| `Chappy_Trading_Opportunity_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Opportunity_Study_v0.1(2).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Opportunity_Study_v0.1(3).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Opportunity_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Order_Flow_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Paired_Variance_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Parallel_Requalification_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Parallel_Review_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Peer_Context_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Pipeline_Crash_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Pipeline_Crash_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Pipeline_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Pipeline_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Portfolio_Decision_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Portfolio_Stress_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Portfolio_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Portfolio_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Post_Switch_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Price_Response_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Qualification_Generation_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Random_Market_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Rare_Evidence_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Receipt_Bias_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Recovery_Requalification_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Recovery_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Refresh_Robustness_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Refresh_Trigger_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Regime_Selection_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Regime_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Regime_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Relative_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Relative_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Requalification_Budget_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.1.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.2.0(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.2.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.3.0(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.3.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.4.0(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.4.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.5.0(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Research_Lab_v0.5.0.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Review_Workflow_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Review_Workflow_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Selective_Hypothesis_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Sequential_Gate_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Sequential_Monitor_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Short_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Short_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Signal_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Signal_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Statistical_Gate_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Stop_Reason_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Supplier_Complement_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Switch_Evidence_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Text_Extraction_Study_v0.1(1).py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Text_Extraction_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Variable_Payoff_Core_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Volume_Baseline_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_Trading_Volume_Context_Study_v0.1.py` | Located by filename; full source review/import pending |
| `Chappy_ZIP_Pair_Splitter_v1.0.0.zip` | Located by filename; full source review/import pending |

Historical JSON results and datasets intentionally excluded from this public inventory. Keep original files in their existing locations.
