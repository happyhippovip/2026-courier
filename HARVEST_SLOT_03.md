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

## Task 9: github adapter non-dict guards (cf414d9d) — CLASS: READY_FOR_INTEGRATION
- RED: 7/7 new nondict tests FAIL vs main's adapter (AttributeError).
- GREEN: 18/18 PASS vs convergence version (isolated /tmp extraction).
- File bucket 14 → CROSS_SLOT_DEPENDENCY (port owns bucket 14). No write.

## Task 10: github dispatcher static read (main, bucket 11, findings only)
- Fire-and-forget Popen per claim: no wait/code check, no log capture;
  crash-before-post relies on lease reclaim. Tolerable, note for owner.
- Unsanitized task_id in /tmp path + `venv/bin/python3`-else-python3
  portability wart (staging fixed this pattern elsewhere).
- Server calls have timeout=10; non-JSON 200 fails closed via outer except.
- No P0. No write.

## Task 11: windows daemon binding (27ee67d4) — CLASS: READY_FOR_INTEGRATION (unit)
- Verified: test_windows_worker_binding.py 8/8 PASS (isolated module
  load, mocked transport). Evidence: UNIT; PHYSICAL_WINDOWS_REQUIRED
  for real daemon crash proof.
- SECRET_FINDING=YES FILE=scripts/windows_worker/daemon.py
  VALUE_REDACTED=YES (main still carries hardcoded fallback credential;
  convergence removes it → env/config + fail-closed require_api_key).
- Release-on-reregister + artifact re-hash before upload read correct.
  No write (reserved runtime + foreign buckets).

## Task 14: intake/dispatcher exception read (main) — findings only (buckets 9/7)
- intake_dispatcher.py:47-48: corrupt central_state.json → silent
  `{"tasks": {}}` reset + non-atomic rewrite (local revenue sidecar;
  limited blast radius, still lossy). External gh dispatch (line 26)
  happens BEFORE any state record → crash gap = orphaned run.
- queue_processor: failures stay pending (good); but dispatch_intake's
  sys.exit(1) aborts whole batch = head-of-line blocking (see task 15).

## Task 15: queue batch fix (d5222821) — CLASS: READY_FOR_INTEGRATION
- `except (Exception, SystemExit)` keeps poisoned intake from dropping
  batch. Verified isolated: 4/4 PASS. Buckets 7/9 → owners port.

## Task 16: adapter fix trio (a133a10a, 1c0fcb4d, 5106447d) — READY_FOR_INTEGRATION
- Verified isolated (/tmp extraction): 30/30 PASS — antigravity job-ID
  fullmatch, gemini path-safe task_id, deterministic_transform str-entry.
- All foreign buckets → owners port. No write.

## Task 17: workflows read-only audit — SUPERSEDED + finding
- main courier_motor.yml still `*/5` cron; staging e6a5a53a already
  replaced with push trigger + idle precheck → SUPERSEDED, no action.
- No timeout-minutes on any workflow; concurrency only on 2/6 files.
  Runaway-spend angle parked for cost owner (no write).

## Task 18: replacement-coverage quality check — CONFIRMED
- caa7cff4 claimed reconciliation covered by
  test_server_integration_contract.py. Verified on main: 19/19 PASS;
  real coverage (quarantine w/o replay, late-result 409, exactly-once
  advance, one-winner claims). Removed file-plane tests genuinely
  obsolete (module eliminated). Claim holds.

## Task 19: dispatcher identity persist-first (c70f8f23 line) — READY
- test_github_dispatcher_identity.py: 14/14 PASS isolated (persist
  before spawn, no double-spawn per process, restart no-redispatch).
- Method note: first run showed 1 failure caused by MY incomplete
  /tmp extraction (missing adapter module), not product. Completed
  extraction → green. No false alarm filed. Bucket 15 → no write.

## Task 20: mac contract + install tests — READY (12/12)
- test_mac_worker_contract.py + test_mac_worker_install.py PASS in
  staging worktree. Lesson repeated: piecemeal /tmp extraction caused
  9 phantom failures (missing transitive deps); full worktree → green.
  Prefer worktrees over extraction for server-importing suites.

## Task 21: windows + credential suites — READY (47/47)
- test_windows_worker_contract/credentials + ci_acceptance_credentials
  + script_credentials PASS on convergence line. Evidence: UNIT/
  CONTRACT (mocked transports); physical proofs still required for
  live daemons. No write (reserved runtimes).

## Task 22 (GOOGLE-05): windows daemon static audit — 1 OPEN finding
- Orphan-on-timeout: run_task Popen + communicate(600), TimeoutExpired
  → FAILED posted, child NEVER killed/waited (zero kill/terminate/
  TimeoutExpired refs in main AND convergence daemon). Orphan may
  complete effect after failure recorded → ambiguous/duplicate effect
  + handle leak. Demo /tmp/orphan_demo.py: child alive after handler.
  Suggested minimal fix (owner writes): except TimeoutExpired →
  process.kill()+wait, distinct TIMEOUT status. PHYSICAL_WINDOWS_
  REQUIRED for live proof. SUPERSEDED-check: convergence fixed
  4xx/5xx split + identity binding but NOT this. No write (reserved).

## Task 12: venv-python portability sweep — findings only (buckets 8/11/16)
- Pattern `"venv/bin/python3" if exists else ...` on main in 3 files:
  run_final_acceptance.py (8, staging already → sys.executable),
  courier_github_dispatcher.py (11, falls back to bare `python3` —
  weakest variant), run_boundaries.py (16). Parked for owners.

## Checkpoint 2
- Slot branch: +2 docs commits pending push with this one.

## Task 13: mac never-re-execute read (9b36ca5d) — READY (unit) + PHYSICAL_MAC_REQUIRED
- Phase-persisted CLAIMED/STARTED/RESULT_READY; atomic persist
  (tmp+fsync+replace); legacy phaseless → STARTED (fail-closed);
  4xx-final/5xx+transport-retry; rejected payload kept.
- Unit tests 18/18 (with p3 batch). Live crash proof still needs Mac.
- Logic sound on read; no write (reserved runtime).
