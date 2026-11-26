# Lean development and research workflow
2026-11-27 JST | Owner direction: adopt only useful CBDK development practices, NOT ABCD organization.
Applies to both Chat and Work, within existing RESEARCH_CHARTER and AUTONOMY_RULES. This does not authorize new tasks, automatic merging, scheduling, holdout access, or restricted-data use.

## One project, one active execution path
No ABCD teams, specialist assignments, commander bureaucracy, extra labs or mandatory handoffs for each tiny action. Work executes bounded research; Chat reviews, preserves history and clarifies direction as needed. Use existing queue, state, lease and PR mechanism; do not build a second coordinator. Keep a single active writer per task. Independent validation is a quality technique, not another permanent team.

## Default cycle (one run where possible)
1. **Refresh selectively:** current main, active claim/PR, relevant queue revision, charter, and only necessary code/evidence. A saved checkpoint is a hint, not proof of current state. Read summaries first; inspect full logs only for failures or required evidence. Reuse unchanged exact-identity evidence without relabeling it a new execution.
2. **Bound the work:** one objective, baseline, acceptance and stop conditions, finite budget. Group related tests that share the same failure mechanism, fixture, authority and acceptance criteria. Keep individual outcomes; do not bundle unrelated work or force a test quota.
3. **Use the simplest useful method:** standard library or existing verified code, then small changes; new algorithms only if a concrete need remains. First make it work, then optimize only on measured material bottlenecks. No speculative refactoring or gratuitous optimization.
4. **Verify:** positive and negative controls; compare on identical frozen conditions; test at exact final source revision. Check synthetic fixture, known data and genuinely unseen evidence separately. If mandatory CI is applicable, inspect its exact-HEAD summary and required job evidence; pending, skipped or failed is not success. No raw/restricted data in CI. When execution is unavailable, report that instead of claiming a pass.
5. **Persist once:** concise task ID, base/final revision, changed files, evidence pointer, result, limitations, remaining gate and next action. Retain detailed logs/results locally under rights restrictions; don't continually rewrite old reports. If another authorized task is ready and capacity remains, continue without asking for each step. Stop at scope completion, blocking dependency, safety issue, exhausted budget or approval boundary.

## Exception-only method audit
Use when evidence contradicts a known control, repeated fixes fail, a simpler method exists, cost exceeds plausible benefit, or task appears complete. Ask: Is the measuring instrument correct? Is the absolute effect relevant to the goal? Is there a simpler existing solution? Does the deliverable actually meet the goal? Start with one cheap discriminating control. Do not repeatedly audit the audit. Report purpose/evidence/decision/next action in up to four lines; no extra normal-run ritual. Do not move acceptance thresholds after observing results.

## Efficiency measurement and adoption
Measure actual calls, duplicated setup, user interventions, elapsed time, and quality only when readily available. No fabricated token/quota savings. A short handoff alone is not proof of faster research. Prefer a simpler procedure unless it removes required evidence; remove redundant steps rather than quality gates. Trial on the next already authorized task, then retain only improvements supported by actual use. Do not launch a standalone process-improvement research project.

## CBDK provenance and limits
Adapted from CBDK research PR #115 at 70fb5701d65449839bcccacffd0d55d0afcf27a9:
- DIL-09 [pilot](https://github.com/mibesamiti-png/Chappy-Blender-DevKit/blob/70fb5701d65449839bcccacffd0d55d0afcf27a9/research/development_intelligence/dil09/PILOT.md): bounded work, current evidence, compact checkpoints, CI summary first.
- [Pilot result](https://github.com/mibesamiti-png/Chappy-Blender-DevKit/blob/70fb5701d65449839bcccacffd0d55d0afcf27a9/research/development_intelligence/dil09/PILOT_RESULT.md): documentation reduction measured, general throughput not proven.
- [Batching proposal](https://github.com/mibesamiti-png/Chappy-Blender-DevKit/blob/70fb5701d65449839bcccacffd0d55d0afcf27a9/research/development_intelligence/batch_execution/BATCH_EXECUTION_PILOT.md): related work in one bounded batch; speed/usage benefit is a hypothesis.
- DIL-10 [method audit](https://github.com/mibesamiti-png/Chappy-Blender-DevKit/blob/70fb5701d65449839bcccacffd0d55d0afcf27a9/research/development_intelligence/dil10/PROTOCOL.md): exception-only, calibration, value, simplicity, actual goal; intervention effect not established.

No CBDK team structure, Blender CI requirements, source implementation or extra approval hierarchy is imported. CTL application is owner-directed operating guidance, not evidence of measured CTL efficiency gains.
