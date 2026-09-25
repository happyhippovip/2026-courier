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

## Next
- Bucket 2 exhausted (1 branch candidate + 3 files). No foreign-bucket
  writes. Ready for final report.
