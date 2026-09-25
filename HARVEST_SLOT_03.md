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

## Next
- Phase B: production files with sha256(path)%32==2 → P0 sweep
  (duplicate execution, volatile IDs, lost persistence, unsafe retries,
  ambiguous crash recovery).
