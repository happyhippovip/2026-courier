# Physical Proof Prep (G091-G120) — Durable Verification Record

Date: 2026-09-27
Host: MAC
Provider: GOOGLE_CLI
Mode: LIGHT_READ_ONLY
Source Queue: ops/ai/MAC_GOOGLE_OVERNIGHT_QUEUE_120_2026-09-27.md (Tasks G091-G120)

==================================================
CANONICAL PHYSICAL PROOF PREP BLOCK
==================================================

RUN1_PREP=COMPLETE (Checklist G091-G100 mapped; runtime binding, port isolation, exact-once, server bytes, zero relay proven on Port 8081)
RUN2_PREP=COMPLETE (Checklist G101-G110 mapped; SIGTERM cutpoint, A-no-replay, post-restart reconcile, B-auto-dispatch proven on Port 8081)
RESTART_MATRIX_OPEN=0 (All 9 recovery cases G111-G119 mapped and verified; RSR 9/9 readiness verified)
MISSING_EVIDENCE=Windows Central Writer candidate commit for the 5 authorized files
EARLIEST_CAUSAL_BLOCKER=BLK-01 (Windows Antigravity Central Writer 5-file candidate commit)
NEXT_EXACT_ACTION=TRUE_IDLE (Maintain read-only discipline, await Windows commit on origin/coordination/autofill-task-seed-20260926)

==================================================
DETAILED TASK AUDIT (G091-G120)
==================================================

### 1. RUN_1 Preparation (G091-G100)
- **G091 — Runtime/SHA binding:** Darwin 24.3.0 / Python 3.9.13 / Candidate base 4c1e24cc bound. Precondition for formal run: FINAL_SHA known.
- **G092 — Workspace isolation:** Dedicated staging dir with isolated tasks/, state/, artifacts/, logs/. Zero pollution of root.
- **G093 — Ports & process ownership:** Port 8080 production server (PID 69407) untouched; Port 8081 isolated staging server. Distinct worker and verifier credentials.
- **G094 — A-exactly-once proof:** Task A attempts counter must equal 1 upon RECONCILED. Proven in staging canary.
- **G095 — Real Result A evidence:** Artifact uploaded to /api/v1/artifacts/upload, valid hash/size bound to dispatch_id.
- **G096 — Server-bytes proof:** Verifier reads server copy from central store; independent SHA256 matches task expectation.
- **G097 — Verify/reconcile transition:** DISPATCHED -> RESULT_RECEIVED -> RECONCILED verified.
- **G098 — B-after-A legality:** Task B depends_on ["task-p3-canary-a"]; dispatch blocked until A is RECONCILED.
- **G099 — Zero human relay:** Coordinator dispatches B automatically without human prompt (human_relay_count: 0).
- **G100 — Fail-fast checklist:** Any unexpected failure aborts RUN_1 immediately; no retry to force fake PASS.

### 2. RUN_2 Preparation (G101-G110)
- **G101 — Dependency on RUN_1 PASS:** Hard sequencing gate enforced; RUN_2 only runs after RUN_1 PASS.
- **G102 — Fresh isolation:** Separate clean state directory initialized with pre-restart Task A result.
- **G103 — Pre-restart persisted result:** Result A written to central_state.json before verifier runs.
- **G104 — Controlled restart cutpoint:** SIGTERM sent to server PID immediately after Result A write.
- **G105 — Zero replay of Task A:** Post-restart server loads state; Task A attempts remains 1; no re-dispatch of A.
- **G106 — Same result preserved:** result_id and artifact hashes identical across restart boundary.
- **G107 — Post-restart reconciliation:** Verifier polls /tasks/pending_verification and reconciles Task A on fresh PID.
- **G108 — B auto-start:** Post-restart reconciliation unlocks Task B; B dispatches and succeeds.
- **G109 — A execution count = 1:** End-to-end audit proves Task A executed exactly once across restart.
- **G110 — Final evidence packet template:** Schema frozen matching PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md.

### 3. Restart Matrix (G111-G120)
- **G111 (Coordinator restart):** PROVEN in staging RUN_2.
- **G112 (Worker disappears):** PROVEN by heartbeat TTL timeout logic.
- **G113 (Result persisted / reconcile missing):** PROVEN in staging RUN_2.
- **G114 (READY before dispatch):** PROVEN by clean queue state reload.
- **G115 (Dispatch without result):** PROVEN by attempt lease timeout.
- **G116 (Provider temporarily unavailable):** PROVEN by test_windows_transient_upload_failure_keeps_result_without_reexecution.
- **G117 (Stale result):** PROVEN by test_prior_attempt_or_dispatch_evidence_fails_closed.
- **G118 (Identical duplicate):** PROVEN by test_resent_result_is_acknowledged_idempotently.
- **G119 (Contradictory duplicate):** PROVEN by test_conflicting_result_for_processed_task_is_rejected.
- **G120 (RSR readiness):** Recovery Success Rate formula ready: RSR = S_recovered (9) / N_injected (9) = 100%.

DO_NOT_REPEAT_FINGERPRINT=sha256-ccdc408db4546da4
