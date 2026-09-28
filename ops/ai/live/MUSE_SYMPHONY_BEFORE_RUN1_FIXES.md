# BEFORE_RUN1 Fixes — Completed 2026-09-28

STATUS=FIXES_COMPLETE
TESTS=98/98 PASS + 12/12 Verifier Self-Tests PASS

## Fix 1: Verifier Negative Idempotency (CONFIRMED_SOURCE_DEFECT → FIXED)
FILES=server/app.py (verify_task_result)
BUG=Retried FAIL verdict on FAILED_VERIFICATION task returned 409 instead of ACK_DUPLICATE.
FIX=Extended duplicate guard to cover both RECONCILED and FAILED_VERIFICATION statuses.
TEST=test_verify_fail_duplicate_returns_ack_not_409 (PASS)

## Fix 2: Synthetic-Reject-Gate (WB01-Minimal → IMPLEMENTED)
FILES=scripts/run1_physical/verify_proof_contracts.py, scripts/run_physical.py
BUG=Stub producer could generate false-green RUN_1 PASS because verifier had no synthetic detection.
FIX=Added verify_not_synthetic() fail-closed gate + "synthetic": true label in stub producer.
TEST=Verifier self-test #12 (synthetic reject negative test) PASS

## Fix 3: RUN_2 Verifier Contract Bug (CONFIRMED_SOURCE_DEFECT → FIXED)
FILES=scripts/run1_physical/verify_proof_contracts.py (verify_b_continuation)
BUG=Blanket `assert st != 'VERIFY'` would reject legitimate B verification states in RUN_2.
FIX=Changed to context-sensitive check: only reject bare 'VERIFY' (A re-verification), allow VERIFY_B/B_VERIFY.
TEST=Verifier self-test suite 12/12 PASS

## Split-Brain (Family 13.2) — ALREADY FIXED
Confirmed: task_result() already syncs step["status"] via _find_workflow_step (lines 420-425).
No additional fix needed.

REMAINING_BEFORE_RUN1=
- Real producer ausbau (run_physical.py muss echte HTTP-Requests an den Server senden)
- compute_run1_chain() im Verifier aktivieren (dead code)

## Fix 4: Hash Chain Dead Code Activation (EVIDENCE_GAP → FIXED)
FILES=scripts/run1_physical/verify_proof_contracts.py (compute_run1_chain, verify_run1_directory)
BUG=compute_run1_chain() was defined but never called. Proof Card claimed hash chain integrity
without any actual verification. Additionally, the function used a different hashing algorithm
(glob *.log/*.json) than the producer (os.walk all files except hash files), so even if called,
the hashes would never match.
FIX=1. Aligned compute_run1_chain algorithm with producer's compute_dir_hash.
2. Added hash chain verification call in verify_run1_directory when falsifiability_hash.txt exists.
TEST=Verifier self-test suite 12/12 PASS

## Fix 5: RUN_2 Verifier Contract (verify_b_continuation) — see Fix 3 above

## Summary
TOTAL_FIXES=4 distinct code changes
TOTAL_FILES_MODIFIED=3 (server/app.py, scripts/run1_physical/verify_proof_contracts.py, scripts/run_physical.py)
TOTAL_TESTS=98/98 unit tests PASS + 12/12 verifier self-tests PASS
REGRESSION=ZERO
