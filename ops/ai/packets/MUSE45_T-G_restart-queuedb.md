# MUSE-45 T-G — Restart/recovery coverage + queue.db artifact gap (read-only)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Method: static tree evidence only (shell DOWN). Nothing modified but this packet.

## Restart/recovery coverage map (OBSERVED)

- Motor level: tests/test_restart_resume_torture.py uses REAL subprocess runs
  (courier script `--run` twice, resume across runs). Exists, mock-free shape.
- Daemon marker level: tests/test_windows_daemon_completeness.py
  TestPersistMarkerRecovery (atomic effect/result marker persist, .tmp hygiene).
  In-process unit shape.
- Daemon LIVE kill-recovery (kill -9 a running daemon mid-job, restart, prove
  job recovery): no test seen. Google's next-task #3 ("restart recovery live
  test") gap is PLAUSIBLY OPEN in its live flavor. Owner scope; needs machine.

## queue.db: absent from tree, required by 2 tests

- `scripts/windows_worker/state/`: EMPTY or missing (glob lists nothing) — no
  queue.db anywhere in tree (binary-aware re-check confirms the T-A result).
- tests/test_windows_daemon_completeness.py:221-237 TestQueueDBSchema asserts
  queue.db EXISTS at scripts/windows_worker/state/queue.db with a
  background_jobs(job_id, task_id, pid, status, started_at) schema.
- Consequence: on this tree those 2 tests cannot pass without a prior daemon
  run that creates the db (runtime-generated artifact, gitignored — see below).
  Google's checkpoint claim "queue.db functional" is therefore live-machine-only
  with zero tree evidence; it is neither confirmed nor disproven from here.
- Suite-shape note for owner: tests that require a live-created artifact fail on
  a fresh checkout. Either the db-creating step belongs in a fixture/setup path
  or these two are documented live-only. Owner call; no edit by me.

## .gitignore check (CONFIRMED)

- `.gitignore:95-101` ignores `scripts/mac_worker/state/` and
  `scripts/windows_worker/state/`. queue.db is therefore a runtime-generated,
  gitignored artifact: absent-from-tree is EXPECTED, and the 2 TestQueueDBSchema
  tests structurally require a live daemon run first. No contradiction — but the
  suite is not fresh-checkout-green without that run. Owner call (fixture vs
  documented live-only).
