# Pre-Codex Harvester Attestation & Hand-off — 2026-09-27

Host: MAC (Auto-Resolved: /Users/user/Downloads/2026-courier)
Provider: GOOGLE_CLI
Role: COURIER RESULT HARVESTER
Policy: ops/ai/RETURNED_RESULT_POLICY.md

==================================================
1. HARVESTED RESULT VALIDATION
==================================================

- Target Claim: PRE-CODEX-GATE-FINAL
- Worker: COURIER_WINDOWS_CENTRAL_WRITER
- Candidate SHA: 9f219f187a415ffef8b6c867b2ff9c26ad0a5b88
- Base Lineage: candidate-b-1 @ 4c1e24ccc522042af826bc4c2b595daf85d097f9
- Classification: PROVEN (All 12 acceptance criteria pass)
- Scope Compliance: Exactly 5 authorized files (4 modified, 1 unchanged, 0 unexpected)
- Targeted Test Evidence: 44/44 PASSED (7.28s), SKIPPED=0
- Formatting Evidence: git diff --check clean (0 trailing whitespace errors)
- Identity Fingerprint: SHA256 of 5-file patch + test runs

==================================================
2. ACCEPTANCE MATRIX TRANSITION
==================================================

Prior Base State (4c1e24cc): 5 PASS, 7 FAIL
Candidate State (9f219f18): 12 PASS, 0 FAIL (12/12 100% PASS)

1. Task Expected Artifact Coverage: PASS
2. Omission Bypass Test: PASS
3. Correct Server Bytes PASS: PASS
4. Wrong Server Bytes FAIL: PASS
5. Worker Expected Hash Rejection: PASS
6. Worker Expected Hash Omission: PASS
7. Legacy No-Task Expectation: PASS
8. Malformed Target Fail-Closed: PASS
9. Verifier Poison Pill Resilience: PASS
10. Result Schema Boundary: PASS
11. Identical Replay & Reload ACK: PASS
12. Changed Metadata Reject: PASS

==================================================
3. DEPENDENCY & QUEUE UNLOCK
==================================================

- PRE_CODEX_GATE: UNLOCKED
- Support Queues: EXHAUSTED & FROZEN
- Unlocked Ready Work: CODEX_HIGH_ONCE
- Final Review Target: 9f219f187a415ffef8b6c867b2ff9c26ad0a5b88
- Harvester Status: TRUE_IDLE

DO_NOT_REPEAT_FINGERPRINT=sha256-4f0cba1231792897
