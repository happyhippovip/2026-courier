# O52 — Adversarial Shared-Capability / Update Red-Team

Status: OPUS_4_6 / C4 / READ_ONLY
Rules:
- RESULT_REUSE_FIRST=YES
- NO_BROAD_REPO_SCAN=YES
- NO_DUPLICATE_REVIEW=YES
- NO_IDLE_ANALYSIS=YES
- NO_BUSYWORK=YES
- UNKNOWN stays UNKNOWN
- no application-source edits
- no Codex invocation
- no physical RUN_1/RUN_2
- unchanged PRE_CODEX fingerprint is not work
- deterministic C0/C1 work must be routed away from Opus
- one live claim per task
- provider limit -> persist once, stop probing, route through provider-limit recovery


Purpose: attack the future concept semantically so unsafe assumptions are found before implementation.

Tasks:
O52-01 Malicious capability pack threat model
O52-02 Compromised publisher/release key scenario
O52-03 Capability dependency confusion
O52-04 Hidden customer-data leakage through generalized packs
O52-05 License/provenance contamination
O52-06 Rollback to vulnerable version
O52-07 Revoked pack still cached/installed
O52-08 Supply-chain downgrade attack semantics
O52-09 Cross-user telemetry privacy risk
O52-10 Unsafe auto-install consent edge cases
O52-11 Capability-name/identity collision
O52-12 Crypto-agility migration failure
O52-13 Final O52 synthesis

Do not build exploit code.
Output only threat, causal impact, containment requirement, evidence needed.
