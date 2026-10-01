# DISPATCHER REVIEW — duplicate-dispatch guards (static, read-only)

File: scripts/courier_github_dispatcher.py. No edits (foreign/service scope).

## Guarded GOOD (corroborated + test-pinned, 13 tests in test_github_dispatcher.py)
- Atomic task-file materialize: O_EXCL tmp + hardlink-into-place keyed by
  sha256(dispatch_id); conflicting packet for same dispatch raises, identical
  concurrent materialize is idempotent.
- Single-flight: claims only when active_procs empty; adapter exit 75
  (WAITING) relaunches the SAME durable dispatch without a second claim.
- Bounded adapter recovery: 3 restarts then fail-closed (no infinite respawn).
- Restart recovery: symlink/identity guards, POSTED checkpoint cleaned without
  replay, >1 unfinished or corrupt persisted task => hard fail-closed.

## Residual notes (unpinned, owner triage)
G-4 (LOW) Claim->persist window: server claim succeeds, then a crash before
  persist_task_file leaves a server-side dangling claim with no local file;
  restart claims a NEW task. Net exists server-side (/tasks/reclaim_stale,
  observed 200s in daemon log). Suggest owner confirm reclaim timeout <
  acceptance idle budget; no code change proposed.
G-5 (LOW-MEDIUM, Windows-path) launch_adapter spawns via "venv/bin/python3"
  or bare "python3" — PATH-dependent, NOT the service venv (.venv_service)
  that runs the dispatcher itself. On Windows acceptance, missing/wrong
  python3 => adapter start failure or wrong env. Suggest: sys.executable.
G-6 (LOW) Static WORKER_ID "GITHUB-DISPATCHER" + hardcoded platform "linux":
  second dispatcher instance aliases the first (same class as P-3); platform
  label lies on Windows (routing uses capabilities, likely cosmetic).
G-8 (LOW) Poison-file crash loop: recover_adapters raises on invalid/multi =>
  process exits nonzero => task restarts (good) but the poison file remains =>
  bounded restart budget (3) burns, then manual cleanup. Fail-closed and
  visible; no self-healing. Suggest: quarantine dir for invalid files.

## Net
Duplicate-dispense core is the best-guarded path reviewed this session.
G-5 is the only item with acceptance-path bite (Windows interpreter).
