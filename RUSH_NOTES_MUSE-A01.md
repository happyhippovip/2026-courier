# RUSH NOTES — muse/MUSE-A01-rush-20260925 (from origin/main 3e2fe24d)

Own worktree: /private/tmp/muse-rush-01. Own branch, no peer commits.
Slot-07 branch is peer-owned (stop-write) → this separate rush line.
No main push/merge, no force, no reset/clean, no foreign-tree writes.

## Fixes (each verified RED→GREEN, pushed)

### 1. fea5f719 test_canary.py import-safe via main-guard
- RED (static proof, lines 1-63 all module-level): ~10 live HTTP calls at
  import (register worker, submit goals, claim/result tasks). Bare-root
  pytest collection fires them at whatever listens on 127.0.0.1:8080.
- Fix: body into main() + __main__ guard; dead json/time imports dropped;
  credential line hash-verified byte-identical (SECRET_FINDING=YES,
  VALUE_REDACTED=YES, pre-existing, untouched).
- GREEN: py_compile OK; collect-only → "no tests collected"; import with
  rigged requests.post/get raising → IMPORT_SAFE. Never executed live
  (would write to foreign live server).

### 2. 01378779 test_agy.py import-safe via main-guard
- RED: spawned `agy -p ... --dangerously-skip-permissions` at import.
- Fix + GREEN: same pattern; rigged subprocess.Popen import test clean.
- Convergence line deletes this file (6260706e); guard is compatible
  (deletion wins on integrate, no textual conflict of substance).

### 3. 71f10c47 test_retry.py guard ported from own slot-07 9ec1f76d
- Keeps rush line self-contained (all 3 root smoke scripts guarded).

## Verification (isolated, targeted)
- tests/ full run (minus 3 known collection-broken files): 60 passed, 5.83s.
- Rush tree git status clean after run (no ledger/state pollution).
- Bare-root collect-only: 60 collected + 4 collection errors (all pre-existing,
  none caused by this branch):
  - tests/test_human_gate_truth.py: missing capability_registry (impl only on
    legacy lines) → needs implementation port (integration decision, no write).
  - tests/test_integration_contract.py: missing courier_control_plane
    (eliminated by 575f3893) → fix EXISTS on slot-03 branch (92197787,
    unmerged): SUPERSEDED, not duplicated.
  - tests/test_snitch_watchdog.py: missing resource_intelligence (legacy
    lines only) → same as human_gate_truth.
  - test_daemon_sync.py: dead, calls retired loop() → deletion EXISTS on
    convergence lines (95f496d7, unmerged): SUPERSEDED, not duplicated.
- Convergence strategy note: EHVC pytest.ini scopes collection to tests/
  (95f496d7). Complementary to these guards, not a substitute (manual
  scripts stay runnable + import-safe). Not ported (their lane).

## Read-only findings (no writes — foreign/parked lanes)
- Windows daemon main gaps: no result-identity binding (fixed on
  origin/claude/task03-windows-worker-binding, 2-file change +215-line
  test) → SUPERSEDED; result dropped after retries (task03 adds
  persist_task + rejected quarantine); hardcoded LAN URL + prod key still
  on task03 too → SECRET_FINDING redacted; 401→backoff no fail-fast
  (parked product decision); tasklist PID substring check is /FI-narrowed,
  low severity only.
- Mac daemon main: register loop retries permanent 401 every 5s
  (daemon.py:153-165; committed worker.log shows live 401 busy-loop);
  bare except: at :125. Finding only (Mac runtime reserved).
- queue_processor crash-between-dispatch-and-move → re-dispatch duplicate
  still open after d5222821 (SystemExit-batch fix); file multi-peer
  contested → finding only.
- Dead-import lane saturated: AST F401 scan (100 hits) ∩ files untouched
  since 09-23 = EMPTY. No unowned import fix remains.
- cannon_motor.py does NOT exist on main (branch-only work).
- scripts/artifact_store.py absent on main (server-owned artifact upload
  lives on claude/codex lines) → integration gap for owner lanes.
- agent/integrate-a01-guards on stale base e7d047d9, holds none of the
  4 convergence tips → rebase call for its owner.

## Deferred
- Manual live re-runs of smoke scripts (foreign live server on :8080).
- All parked product decisions (401/403 fail-fast, force_success removal,
  reconcile resurrect).
