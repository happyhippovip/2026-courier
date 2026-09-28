# MUSE ENDGAME C2 — FAMILY=FAILED_EXECUTION_SEMANTICS (local line)
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- GATE: PRE_CODEX=DURABILITY_PENDING (kein Re-Validation, kein Gate-Touch)
- MODE=READ_ONLY_ADVERSARIAL_QA (keine Source-Edits, keine physischen RUNs, keine Full Suite)
- REUSE=FAIL_SEM_AUDIT_result.md → FAILURE_SEMANTICS_AUDIT_2026-09-28.md (12 Cases, scoped auf Base 4c1e24cc); p3-Tests; failure-recovery-matrix
- ORACLE=tests/test_p3_server_idempotency.py 23/23 grün; tests/test_failure_recovery_matrix.py 26/26 grün (Dummy-Env, isoliert)

## Subcases (6, gegen Source-Truth server/app.py)
1. FAILED attempts<3 → QUEUED + Worker freigegeben + Step-Sync (`app.py:388-391,398-402,406-408`) → NO_ISSUE
2. 3. FAILED (attempts=3, Claim zählt `:350-351`) → FAILED_TERMINAL + Goal BLOCKED (`:392-404`) → NO_ISSUE
3. Verify-FAIL → FAILED_VERIFICATION + Goal BLOCKED (`:508-510`) → NO_ISSUE
4. Stale-Worker → HUMAN_REQUIRED-Quarantäne, nie Auto-Replay (`:416-454`) → NO_ISSUE
5. Resume (retry) → QUEUED in Task+Step, Goal ACTIVE; force_success → 400 (`:531-549`) → NO_ISSUE
6. Audit Cases 2/7 behaupten 3-Tuple-Dedup ohne worker_id (Base 4c1e24cc); lokale `:367` prüft 6 Felder inkl. worker_id/attempt_id/artifacts → Doc-GAP-Text stale für diese Linie; STALE-Report nennt das Audit nicht → EVIDENCE_GAP (neu, begrenzt)

## Einziger offener Punkt
- EVIDENCE_GAP: FAILURE_SEMANTICS_AUDIT Cases 2/7 (GAP + Case-12-Blocker) auf diese Linie re-scopen oder als base-gebunden markieren. OWNER=Audit-Author. BEFORE_RUN1 (RUN_1-Witness darf sich nicht auf überholte Blocker berufen). Kein Source-Defect → kein Fix, kein Test.

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-endgame-failed-exec-01
FAMILY_COMPLETE=YES
