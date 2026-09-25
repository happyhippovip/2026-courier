# HARVEST SLOT 07 — RUN 20260925-HARVEST-A (bucket 6)

Claim: `muse/claims/20260925-HARVEST-A-slot-07` (6134ff8f)
Work branch: `muse/run-20260925-HARVEST-A-slot-07` (from origin/main 3e2fe24d)
Bucket scheme: SHA256(repo-relative path) % 32 over tracked `*.py` (matches slot-03 bucket-2).
Bucket-6 files: `scripts/run_academy_demo.py`, `test_retry.py`,
`tests/test_server_integration_contract.py`.
Shared checkout is foreign-writer active (agent/integrate-a01-guards + canary
torture files) → all work in private worktree, read-only elsewhere.
No main push/merge, no force, no reset/clean.

## Candidates (prior, carried from checkpoint)

### 1. claude/task05-integration-contract-test — CLASS: READY_FOR_INTEGRATION
- 1 commit 29397352; main=collection ERROR, branch=8 passed/5 skipped.

### 2. muse/MUSE-A01-yolo-done-fallback-binding — CLASS: READY (CHERRY-PICK ONLY)
- 13/13 on 2 P0 binding test files. Never merge (~3224 files incl. logs/work_dir).

### 3. agent/cannon-v1-retry-semantics2 — CLASS: SUPERSEDED
- Ancestor of yolo-branch, same lineage.

## Phase B: P0 sweep — bucket-6 production files

### scripts/run_academy_demo.py — CLASS: KEEP (no P0, no patch)
- Academy demo script, not on the Cannon-V1 result path. Stage asserts
  (APPROVED_FOR_TEST/PASS) are demo-local; no attempt/dispatch/result
  identity is minted or rebound here. No retry-vs-resend risk.
- Findings (documented, NOT patched — cross-bucket / no-cosmetics):
  - Hardcoded `/Users/user/Downloads/2026-project-memory` default shared
    with 14 sibling scripts. Canonical fix (shared helper/env override)
    lives in buckets 13/14 (`scripts/run_academy.py`,
    `scripts/run_context_sync.py`). No one-off knob from this slot.
  - `--reset` CLI flag is dead surface: no reset/clear/purge API exists in
    the academy modules and nothing references the flag. Left in place
    (removal is CLI-surface churn with zero functional gain).

## Phase C: bucket-6 tests vs invariants

### tests/test_server_integration_contract.py — CLASS: KEEP (verified CONTRACT)
- `pytest tests/test_server_integration_contract.py -q`: 19 passed in ~6s.
- Real invariant coverage over Flask test_client + real tmp state file
  (no behavior mocks): claim identity fields, verifier independence
  (self-cert 400, forged verifier 401, shared-key 503), wrong-attempt 400
  fail-closed, retry mints `attempt:2` + fresh dispatch, one-active-task
  (WORKER_BUSY), re-register preserves claim, concurrent claims
  exactly-one-winner, stale quarantine + late result 409, corrupt state
  raises instead of treated-as-empty, insecure-default 503, background
  agents fail-closed without keys.
- Worktree `git status` clean after run (no ledger/state pollution).
- Limitation (not a defect): concurrency test coordinates in-process
  `save_state`, so it proves single-process mutual exclusion, not
  cross-process locking. Mark evidence CONTRACT (single-process).

### test_retry.py — CLASS: BROKEN → FIXED (own bucket)
- RED BEFORE: module-level live HTTP at import; bare `pytest` from repo
  root died with `ERROR collecting test_retry.py` (KeyError: 'task').
  Worse, collection fired real register/goal/claim/result calls at
  whatever listens on 127.0.0.1:8080 (a foreign live server answered
  during the probe — left untouched, no further pokes).
- Fix (9ec1f76d on this branch): body moved into `main()` under
  `if __name__ == "__main__":`; dropped dead `json, time` imports;
  docstring marks it manual-only. Credential line byte-identical.
- GREEN AFTER: `pytest --collect-only test_retry.py` → "no tests
  collected", no network (import with rigged `requests.post/get`
  raising prints IMPORT_SAFE_NO_NETWORK); bucket collect →
  19 tests, 0 errors.
- Manual re-execution (`python3 test_retry.py`) deliberately NOT run:
  it would write to the foreign live server. Equivalence by
  construction (pure re-indent + same `__main__` entry).

## Findings
- SECRET_FINDING=YES FILE=test_retry.py VALUE_REDACTED=YES
  (committed hardcoded Bearer credential, pre-existing, untouched).
- Live process note: something serves 127.0.0.1:8080 (foreign). No
  live-server pokes beyond the one accidental pre-fix collection probe.

## Deferred gates
- None.

## Next
- Bucket 6 exhausted (3 prior candidates + 1 prod file + 2 test files).
  No foreign-bucket writes. Ready for final report.
