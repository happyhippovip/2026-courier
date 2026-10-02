# WIN-BB-01 PKG-C — 12-case evidence matrix (current SHA 329abd80)

Scale: PROVEN_BY_CODE (PBC) / TEST_EXISTS_NOT_EXECUTED (TENE) / PHYSICAL_PROOF_REQUIRED (PPR) /
CONTRADICTED / UNKNOWN. Nothing is PROVEN_BY_EXECUTED_TEST (shell down, zero runs).
"12_CASE/RUN1/RUN2/FINAL_CANDIDATE" still zero hits in-tree → case definitions = mission text.

1. task-owned expected hash survives Goal→Claim→PendingVerification — PBC + TENE.
   submit_goal stores artifacts verbatim (:110-118); claim copies whole step incl artifacts (:327-347,
   prepare_task passes artifacts through); pending returns task (:456-464); verifier reads
   task.artifacts[].expected_sha256 (:77-80). Pin: test_verifier_checks_expected_sha256 (setup→claim→
   pending→verify). BOUND: enforced ONLY in upload lane (see case 5).
2. correct server bytes PASS — PBC + TENE. put server-hash (:94) → check_reference (:133-144) →
   verifier re-hash + binding equality (:86, verify_uploaded_artifact :147-159) → server equality gates
   (:487-491) → PASS→RECONCILED. Pins: test_upload_then_result_reference_is_accepted,
   test_verifier_independently_hashes_server_copy (PASS leg), windows E2E reconcile.
3. wrong server bytes FAIL — PBC + TENE. Same chain; tampered blob → verifier hash mismatch → FAIL
   (:83-85, :150-151); server records FAILED_VERIFICATION + BLOCKED (:508-510). Pins: tamper legs of
   the two tests above (blob.write_bytes(b"tampered") → FAIL).
4. worker expected hash rejected — PBC (+ adjacent TENE, dedicated pin MISSING).
   validate_durable_result artifact key-set must be EXACTLY {path,sha256} or {path,sha256,artifact_id,
   size} (contract :155-156); a worker-supplied expected_sha256 key → ContractError → 400 (:380-381).
   Adjacent pin: test_contract_rejects_malformed_references_and_windows_paths (shape strictness, but
   no expected_sha256-key case). TEST_TO_ADD: post result with artifacts:[{path,sha256,expected_sha256}]
   → expect 400.
5. worker omission cannot bypass task expectation — PBC for remote/upload lane + TENE; GAP in local
   lane (BB01-NEW-1, MEDIUM — see Central Writer input). Remote: non-uploaded ref → verifier FAIL
   (:90-92, pin test_verifier_never_opens_remote_worker_paths) + default-OFF upload (V-PKG3-1) means
   omission fails closed. Upload lane: expected enforced (:82-85). LOCAL lane (linux/github, hash-only
   refs): verifier checks only worker-claimed sha vs local file (:93) — task expected_sha256 NEVER
   consulted; server check_reference skips hash-only refs. A linux worker honestly reporting sha(Y)
   for Y≠expected passes local_verify → RECONCILED with wrong content. No test covers local+expected.
6. missing task expectation remains legacy, not exact-content — PBC + TENE. String-form artifacts
   (no dict/expected_sha256): upload requires name-in-expected (:189-191) but no content ground truth;
   chain binds worker bytes consistently (put→ref→re-hash) without exactness claim. Pin: legacy string
   artifacts accepted (test_upload_then_result_reference_is_accepted uses ("win.txt",)).
7. malformed/ambiguous target FAIL — PBC only (no dedicated pin found). Verifier :65-68 FAILs targets
   outside {linux,windows,mac,github}; claim-side: unmatched target → no dispatch, task stays QUEUED
   (:282-292 fallthrough → None). TEST_TO_ADD: verify_artifacts({target_capability:"weird"},…) → FAIL.
8. identical replay ACK incl persistence/reload — PBC + TENE (reload leg PPR). Result resend exact
   9-field → ACK_DUPLICATE (:367-368); verify resend same result_id → ACK (:476-480); daemon redelivers
   persisted RESULT_READY without recompute (daemon :335-337 + :342). Pins: test_resent_result…,
   test_resent_failed_result…(after requeue), windows transient-fault no-reexec. GAP: no test kills the
   server process and resends after reload (atomic save makes it safe by construction :65-72, but
   unpinned) → PPR for the reload leg.
9. changed status ≠ duplicate success — PBC (+ conflict-family TENE). 9-field equality includes status
   (:367); changed status → falls to 409 terminal-conflict (:369-370). Adjacent pins: conflict 409 +
   changed-artifacts 409 (test_p3:92-118). No SUCCESS→FAILED-same-ids pin — trivially covered by code;
   optional TEST_TO_ADD.
10. changed worker ≠ duplicate success — PBC (no dedicated pin). Stored-compare includes worker_id
    (:367); mismatch → 409 if terminal (:369) else 400 worker-check (:372-374). TEST_TO_ADD (cheap).
11. changed attempt/dispatch rejected — PBC + TENE. validate :139-141 mismatch → 400; resume mints
    fresh IDs making old results unbindable (:534-536). Pin: superseded-attempt 400 (test_p3:64) +
    upload binding-mismatch 400s (upload_flow:60-68).
12. changed artifact result ≠ duplicate success — PBC + TENE. artifacts in 9-field equality (:367);
    changed → 409 + stored preserved (:369-370). Pin: test_changed_result_not_duplicate_success +
    test_conflicting_result… (stored result_id preserved).

TALLY: PBC all 12; TENE 8 (1,2,3,5-remote,6,8-noreload,11,12); PPR 1 leg (8-reload); dedicated-pin gaps
4,7,10 (+9 optional); NEW GAP BB01-NEW-1 (case-5 local lane). Zero CONTRADICTED.

CENTRAL_WRITER_INPUT BB01-NEW-1 (MEDIUM, verifier scope):
FILE=scripts/courier_verifier.py FUNCTION=verify_artifacts LINE_OR_REGION=:93 elif-local branch.
DEFECT=local lane (linux/github hash-only refs) never consults task-owned expected_sha256; it checks
worker-claimed sha against the local file only. CURRENT_BEHAVIOR=task expects X, worker produces Y≠X
and honestly reports sha(Y) → local_verify passes → server gates (result_id+artifacts equality) pass →
RECONCILED with content violating the task expectation. REQUIRED_BEHAVIOR=when task.artifacts[] holds
{path,expected_sha256} for the ref path, the local branch must ALSO require local-file hash ==
expected_sha256 (same rule as upload branch :82-85); absence of expectation keeps legacy behavior
(case 6). WHY_IT_MATTERS=exact-content guarantee silently degrades to worker-claimed consistency on
the local lane; a task owner setting expected_sha256 gets no enforcement there. TEST_TO_ADD_OR_RUN=
test_verifier_local_lane_checks_expected_sha256 (linux target, dict artifact with expected, local file
with different bytes + worker sha of actual → FAIL; matching → PASS). DO_NOT_CHANGE=upload branch,
remote refusal, legacy string-artifact path, server equality gates.
