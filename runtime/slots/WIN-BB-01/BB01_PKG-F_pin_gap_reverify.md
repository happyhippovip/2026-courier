# WIN-BB-01 PKG-F — 12-case pin-gap reverify (repo-wide, vs PKG-C)

Goal: verify PKG-C's "no dedicated pin" claims across ALL of tests/ (34 files), not just the five
backbone files. Method: regex search for worker-change / malformed-target / expected-key scenarios
+ full reads of tests/test_failure_recovery_matrix.py (98L) and the contract-shape region of
tests/test_artifact_store.py (:85-117). All verdicts static (shell down, 0 runs).

## Result: 2 refinements (adjacent pins PKG-C missed), 3 gaps CONFIRMED, 1 gap narrowed

1. Case 10 (changed worker ≠ duplicate) — REFINED, gap stands in narrowed form. PKG-C: "PBC (no
   dedicated pin)". Repo-wide search FOUND test_result_from_another_worker_is_rejected
   (test_failure_recovery_matrix.py:31-36): registers OTHER, posts FIRST result with worker_id=OTHER
   → 400, stays DISPATCHED. That pins wrong-worker-FIRST-result, NOT the case-10 resend variant
   (stored SUCCESS + resend with changed worker_id → expect 409-via-9-field, i.e. the BB01-4
   strengthening leg). So: case 10 = PBC + adjacent-TENE (first-result variant); dedicated
   resend-variant pin STILL MISSING. TEST_TO_ADD (unchanged, now also pins BB01-4): store SUCCESS,
   resend identical-but-worker_id=OTHER → expect 409 (live) — would ACK under the 3-field patch
   version, so this test guards the strengthening.
2. Case 9 (changed status ≠ duplicate) — adjacent set EXTENDED, pure pin still missing. Found
   test_conflicting_second_result_cannot_replace_first (failure_recovery:20-28): changes
   result_id+status+artifacts together → stored preserved. Mixed-change only; PKG-C's "no
   SUCCESS→FAILED-same-ids pin" CONFIRMED. Optional TEST_TO_ADD stands.
3. Case 11 (changed attempt/dispatch) — pin set EXTENDED. Found
   test_result_with_wrong_identity_is_rejected (failure_recovery:39-44, parametrized
   goal_id/attempt_id/dispatch_id → 400, stays DISPATCHED) IN ADDITION to PKG-C's cited pins
   (superseded-attempt 400 test_p3:64 + upload binding 400s upload_flow:60-68). Also adjacent:
   test_wrong_attempt_result_fails_closed (integration_contract:135-145). Case 11 remains the
   best-pinned idempotency case. No action.
4. Case 4 (worker expected hash rejected) — gap CONFIRMED repo-wide. The adjacent pin exists exactly
   as PKG-C described: test_contract_rejects_malformed_references_and_windows_paths
   (test_artifact_store.py:106-117, 7 malformed cases) — verified by read: NO expected_sha256-key
   case. Zero hits for worker-supplied expected_sha256 anywhere in tests/ (only the task-owned
   uses in upload_flow:143-164). TEST_TO_ADD stands: result artifacts [{path,sha256,expected_sha256}]
   → 400.
5. Case 7 (malformed/ambiguous target) — gap CONFIRMED repo-wide. No test posts an unknown
   target_capability to verify_artifacts or claims an unmatchable target (only unrelated
   "malformed" hits: muse_convergence metrics test, run_boundaries script notes). Verifier :65-68
   FAIL + claim fallthrough-to-None remain code-only. TEST_TO_ADD stands.
6. Case 8 reload leg — gap NARROWED, PPR stands in final form. Found
   test_server_restart_keeps_dispatch_identity_and_accepts_bound_result (failure_recovery:74-81):
   fresh client over the SAME state file + posts the FIRST bound result → 200. This pins
   state-file durability across client reload, but NOT the missing leg PKG-C named (server process
   killed + STORED result resent → ACK_DUPLICATE). So the reload PPR is now precisely: ACK-after-
   true-restart unpinned; durability-across-reload pinned. No test kills the process (no runner).
7. Cases 1,2,3,5-remote,6,12 — pin citations SPOT-CONFIRMED (upload_flow tamper/expected/remote-
   refusal tests re-read in PKG-A verification; no change). Case 5 local lane = BB01-NEW-1 (owned,
   not re-filed). G-BB2 (multi-step A→B unpinned) CORROBORATED: every claim/result test observed
   uses single-step goals; no multi-step sequencing test found.

## Updated tally (supersedes PKG-C tally line only)

PBC all 12; TENE 8.5 (1,2,3,5-remote,6,8-noreload+durability,10-adjacent-first-result,11,12);
PPR 1 leg (8 ACK-after-true-restart); dedicated-pin gaps 4,7,10-resend (+9-optional unchanged);
NEW GAP BB01-NEW-1 unchanged (case-5 local). Zero CONTRADICTED. Delta pins found this package: 4
tests in test_failure_recovery_matrix.py (another_worker, wrong_identity, conflicting_second,
server_restart_durability).
