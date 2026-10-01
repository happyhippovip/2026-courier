# MW1 — Cross-platform contract drift (Mac vs Windows)

MODE=READ_ONLY. No implementation. Static comparison of on-disk worker code.
Contract anchor: `scripts/integration_contract.py` (identity/evidence rules),
`server/app.py` `/tasks/result` (duplicate + acceptance), `/tasks/reclaim_stale`.

Sources (Windows): `scripts/windows_worker/daemon.py`, `stop.bat`, `start.bat`.
Sources (Mac): `scripts/mac_worker/daemon.py`, `runtime_state.py`,
`muse_adapter.py`, `stop.sh`, `start.sh`.

Worktree note (OBSERVED): `scripts/windows_muse_wall/` currently contains only
`runtime/*/state.json`; implementation files are absent, so wall behavior is
out of scope for this comparison. Findings cite current on-disk state only.

Requested output `C:\Users\lol\courier_work\reports\MW1_CONTRACT_DRIFT.md` is
outside this session's writable roots; staged here instead — copy with:
`Copy-Item 'runtime\slots\WIN-01\MW1_CONTRACT_DRIFT.md' 'C:\Users\lol\courier_work\reports\MW1_CONTRACT_DRIFT.md'`

## Explicitly NOT drift (checked, matches contract)

- Identity echo: both workers bind `goal_id/task_id/attempt_id/dispatch_id/
  worker_id` from the dispatch (win daemon.py:185-190, mac daemon.py:541-548);
  attempts are minted server-side per claim (app.py:330-331); neither worker
  mints attempts.
- ID formats differ but are contract-legal: `run_id` PID (win:213) vs UUID
  (mac:547), `result_id` `result-<hex>` (win:192) vs bare UUID (mac:548);
  the contract requires only non-empty strings (integration_contract.py:141-143)
  and the server dedupes on `dispatch_id+result_id+status` equality (app.py:367).
- RESULT_READY redelivers the identical persisted payload on both sides;
  4xx -> REJECTED -> release, 5xx/transport -> UNDELIVERED -> keep
  (win:113-135,344-363; mac:205-217,565-584).
- Restart normalization converges: unknown phase -> STARTED -> release to
  server recovery (win:292-307; mac:426-427,452-460).

## D1 (HIGH) Ambiguous execution: FAILED+orphan vs release+cleanup

- Windows: any execution exception incl. `TimeoutExpired` becomes a FAILED
  result that is persisted RESULT_READY and delivered (daemon.py:211-220,
  336-342). The timed-out child is left running: no kill/terminate/wait
  exists anywhere in the worker code (verified by search; only a tasklist
  *read* for the lock file).
- Mac/MUSE: timeout, output-limit, nonzero exit and unproven cleanup raise
  and release the task WITHOUT a result (daemon.py:372,379,384-389,452-460),
  with ownership-verified group cleanup (`runtime_state.cleanup_group`).
- Contract break: the same physical event yields FAILED+server-retry with a
  live orphan on Windows (duplicate-effect risk when the retry runs) versus
  HUMAN_REQUIRED quarantine on Mac. Breaks AMBIGUOUS_STARTED_SAFE and
  RESULT_READY_NO_REEXEC uniformity.

## D2 (MEDIUM) In-execution heartbeat: absent vs 30s

- Windows heartbeats only at loop top (daemon.py:309-317); `run_task` blocks
  up to 600s (214) with no heartbeat. Reclaim threshold is 300s (app.py:422).
- Mac/MUSE heartbeats every 30s during execution (daemon.py:368-376).
- Contract break: a healthy >300s Windows task is quarantined mid-execution
  and its result then 409s ("not awaiting a result", app.py:373-374),
  orphaning the result; the same-duration Mac/MUSE task survives. (Mac
  agy/native paths share the Windows gap: no in-execution heartbeat, and
  native `subprocess.run` has no timeout at all, mac:275-277.)

## D3 (MEDIUM) Artifact evidence: different safety rule, different base

- Safety rule: Windows rejects absolute/drive/root/`..` under BOTH Windows
  and POSIX rules (daemon.py:151-160). Mac rejects POSIX absolute/`..` only
  (daemon.py:219-225), so Mac can hash and ship drive-qualified paths that
  the server rejects (integration_contract.py:164-168) -> REJECT/release loop.
- Base directory: Windows hashes relative to daemon CWD (`Path(name)`,
  daemon.py:174); Mac resolves relative to `task["workspace"]`
  (`artifact_path`, daemon.py:115,237-240). The same task can bind different
  bytes per platform.

## D4 (MEDIUM) Singleton scope and mechanism are opposites

- Windows host-global temp-dir PID file `courier_worker_{worker_id}.lock`;
  stale check is PID-exists via tasklist substring (daemon.py:248-269).
  PID-alone, reuse-unsafe; same WORKER_ID across checkouts collides.
- Mac: `fcntl LOCK_EX|NB` on `STATE_DIR/worker.lock`, fd held for life
  (daemon.py:392-402). No PID; per-checkout isolation.
- Opposite failure modes: Windows false-refusal/stale-PID risk vs Mac
  permitting two daemons with the same worker_id in different state dirs
  (duplicate-claim exposure).

## D5 (LOW) Storage failure: quarantine vs park-and-retry

- Windows: a persist OSError during/after execution flows into the generic
  handler and the in-memory STARTED task is released to HUMAN_REQUIRED
  (daemon.py:337-342,366-370,298-307).
- Mac: STARTED + storage failure becomes RECOVERY_BLOCKED; the marker is
  preserved and persistence retried, never released, no drain of new work
  (daemon.py:589-592,441-449).
- Same fault yields quarantine on Windows, eventual completion on Mac.

## D6 (MEDIUM) STOP: broad force-kill vs targeted graceful drain

- Windows: `stop.bat` runs `taskkill /F /IM python.exe` filtered only by
  window-title prefix — no PID, no ownership, no graceful drain. The daemon
  has no signal/STOP handling (`__main__` catches only MissingCredentialError,
  daemon.py:378-383). Any matching python.exe dies, foreign or not.
- Mac: `stop.sh` = targeted `launchctl stop`; daemon handles SIGTERM/SIGINT,
  honors STOP-file fencing with an admission lock, and exits cleanly between
  tasks (daemon.py:89-96,450-451,599-606).
