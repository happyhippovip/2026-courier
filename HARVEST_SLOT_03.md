# HARVEST SLOT 03 — RUN 20260925-HARVEST-A (bucket 2)

Claim: `muse/claims/20260925-HARVEST-A-slot-03` (d599da35)
Work branch: `muse/run-20260925-HARVEST-A-slot-03` (from origin/main 3e2fe24d)
Shared worktree is foreign-writer active → productive edits only in private
worktree /tmp/harvest-slot-03. No main push/merge, no force, no reset/clean.

## Candidates reviewed

### 1. codex/canonical-physical-proof-harness — CLASS: NEEDS_VERIFY → VERIFIED (piecewise)
- 1251 files vs main, mostly scratch (w*.txt, website, work_dir). NOT cherry-pickable as a whole.
- Top fail-closed commits (Sep 17) NOT in main (merge-base checked).
- Verified in /tmp isolation: `test_final_acceptance_harness_fail_closed.py` PASSES
  against the branch's `scripts/acceptance/run_final_acceptance.py`
  (refuses default execution with exit 2, SYNTHETIC_TEST_ONLY=YES,
  PHYSICAL_ACCEPTANCE=NO, no state file).
- Main's harness lacks the `COURIER_RUN_SYNTHETIC_ACCEPTANCE=1` gate and still
  labels itself ACCEPTANCE_HARNESS=YES → self-certification risk is REAL on main.
- Files belong to foreign buckets (run_final_acceptance.py=8, test=7, ...) →
  CROSS_SLOT_DEPENDENCY (see below). No cross-bucket write from this slot.

## Cross-slot dependencies (for owning slots, not written here)
- bucket 8: scripts/acceptance/run_final_acceptance.py — needs env-gate +
  secrets.token_urlsafe keys + timeouts (verified logic in candidate branch).
- bucket 7: tests/test_final_acceptance_harness_fail_closed.py — verified test,
  ready to port alongside bucket-8 fix.

## Findings
- SECRET_FINDING=YES FILE=scripts/acceptance/run_final_acceptance.py
  (hardcoded acceptance credential on origin/main; candidate replaces it with
  generated secrets — value never printed here).

## Deferred gates
- None.

## Task 2: tests/test_integration_contract.py (bucket 2) — CLASS: BROKEN → FIXED
- Main's file hard-imports eliminated `scripts.courier_control_plane`
  (removed by 575f3893) → whole P0 contract suite ERRORs at collection.
- Fix already existed on staging/cannon-v1-candidate (caa7cff4, 202-line
  retirement). Verified staging's version: 8/8 PASS against main's scripts.
- Ported ONLY the test-file hunk to slot branch (own bucket), committed,
  pushed (92197787). No rebuild, no duplication.

## Task 3: Phase B P0 sweep — bucket-2 production files
- scripts/courier_verifier.py: reviewed. Verdict re-POST safe (main's
  /tasks/verify: ACK_DUPLICATE on same rid, 409/400 fail-closed, no
  double-advance). No P0. No patch.
- scripts/mac_worker_adapter.py: DEAD CODE — zero callers repo-wide
  (live Mac path is scripts/mac_worker/daemon.py). Latent bugs only
  (makedirs-after-use on timeout path, no task_id path guard, stale
  outbox reuse across attempts). No patch per no-cosmetics rule.
  Resurrect-with-fixes if ever reactivated.
- server/app.py NOT touched (conflict-prone, foreign buckets). Read-only note:
  resume_task force_success mints manual result_id (explicit human action,
  acceptable).

## Task 4: MUSE-B01/yolo-fallback-pin tip (9c8805dc) — CLASS: READY_FOR_INTEGRATION
- Pins yolo_fallback_result_id/read_queue_task (retry-distinct, missing
  record, roundtrip, unreadable) + drops dead code (redundant hashlib
  import, 2 unused except bindings, unused Artifacts assignment —
  verified unused by reading invariants()).
- Verified in throwaway worktree: 11/11 PASS.
- NOT ported to slot branch: depends on peer motor helper chain
  (a75f23e3) absent from main. Integrator cherry-picks with its chain.
- Dedup: slot-02 works dead-import/scratch-cleanup lane — no
  dead-import work from this slot.

## Task 5: safety-hardening tips — CLASS: LINEAGE_DEPENDENT + PREMIUM_REVIEW_CANDIDATE
- 7f235abc (lease_id, ROLE_KEYS auth, HUMAN_REQUIRED guard, win heartbeat,
  courier_status.py) targets a DIVERGED server lineage (keyring role keys,
  old statuses). Main has no lease_id and a different auth model.
- Credential-architecture + P3 server semantics → integrator/Opus decision,
  not a Muse micro-port. Keychain scope reserved. Parked with rationale.

## Task 6: staging/cannon-v1-candidate audit — CLASS: READY_FOR_INTEGRATION (audited parts)
- Real convergence line (23 commits, fresh): scratch fix_*.py deleted,
  pytest.ini scoping, artifact store + verifier re-hash, motor precheck,
  failure-recovery matrix, mac/windows contract tests.
- Verified in throwaway worktree (dummy env): artifact_store +
  upload_flow + motor_precheck = 56 PASSED; failure_recovery_matrix =
  26 PASSED (real state assertions: duplicate ACK w/o state change,
  conflict cannot replace, wrong worker/identity rejected, restart
  keeps identity, unregister quarantine). Evidence: CONTRACT.
- Finding (main-wide, server file, no write): server/app.py import-time
  SystemExit on missing keys kills WHOLE pytest run at collection
  (INTERNALERROR after 75 collected) when any server-importing test is
  collected without env. Owner: P3/server lane.

## Task 7: staging/cannon-v1-extra-high-convergence triage — CLASS: NEEDS_VERIFY→PART VERIFIED
- Superset line (+p3 cutover as docs/patch, adapter fail-closed fixes,
  mac/windows crash binding). Tips: dd3d2644 (p3 patch as files+test,
  respects P3 owner rule), 9b36ca5d (mac never-re-execute + 236-line test),
  27ee67d4 (windows dispatch binding + test).
- Verified in throwaway worktree: test_p3_server_idempotency.py +
  test_mac_worker_recovery.py = 18 PASSED. Evidence: CONTRACT/
  SIMULATED (isolated daemon module + FakeServer; PHYSICAL_MAC_REQUIRED
  for real crash proof).

## Task 8: root smoke-script hazard — PROVEN finding for bucket-1 owner
- main's test_agy.py spawns `agy --dangerously-skip-permissions` at
  MODULE IMPORT. `pytest test_agy.py --collect-only` took 10.78s and
  launched the external agent binary (/Users/user/.local/bin/agy exists).
  Mere collection = arbitrary agent execution. Staging's pytest.ini
  scoping already addresses it; porting belongs to bucket 1, deletion
  to slot-02's scratch lane. No write from this slot.

## Checkpoint
- Slot branch pushed: classify + contract-test fix + this checkpoint.
- Bucket-2 branches: 4/4 triaged. In-bucket files: 3/3 swept.
- NEXT_EXACT_SAFE_TASK: adapter fail-closed read (cf414d9d lineage) and
  dispatcher 4xx/5xx sameness review — findings only (foreign buckets).
