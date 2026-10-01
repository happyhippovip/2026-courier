# MW2 — Windows process-ownership map (worker + supervisor)

MODE=READ_ONLY. No process termination performed or attempted. Static map of
on-disk code: `scripts/windows_worker/*` plus the supervisor scope.
Question per site: is ownership proven by PID, creation time, command line,
parent PID, workspace, or worker ID — and where is PID alone trusted?

Requested output `C:\Users\lol\courier_work\reports\MW2_PROCESS_OWNERSHIP.md`
is outside this session's writable roots; staged here instead — copy with:
`Copy-Item 'runtime\slots\WIN-01\MW2_PROCESS_OWNERSHIP.md' 'C:\Users\lol\courier_work\reports\MW2_PROCESS_OWNERSHIP.md'`

Worktree note (OBSERVED): `scripts/windows_muse_wall/` currently contains
only `runtime/*/state.json` (all `process: null`, e.g. MUSE-01). No
supervisor/slot_state/watcher/ps1 implementation files are on disk, so
supervisor ownership could NOT be verified; `courier_runtime.egg-info/
SOURCES.txt` and `ops/ai/packets/*` references to those files are stale.
The map below covers what exists. No process was touched.

## Ownership-identity matrix (Windows worker, current code)

| # | Site | PID | create_time | cmdline | ppid | workspace | worker_id | Verdict |
|---|------|-----|-------------|---------|------|-----------|-----------|---------|
| 1 | daemon.py:213 `run_id = str(process.pid)` | recorded | no | no | no | no | no | PID-ALONE as identity record; never verified against anything; server requires non-empty `run_id` only |
| 2 | daemon.py:211-220 task child lifecycle | held in Popen object | no | no | no | no | no | NO ownership exercised at all: no terminate/kill/wait on timeout or error; timed-out child orphaned (only tasklist *read* exists, for the lock) |
| 3 | daemon.py:248-269 `acquire_lock` | YES — sole signal | no | no | no | no (filename scope only) | filename only | PID-ALONE TRUSTED: writes raw PID (253), stale check = `tasklist` PID-exists substring (262-263); PID reuse can block a legit start or misattribute liveness |
| 4 | daemon.py:375-376 lock release | path captured at acquire | no | no | no | tempdir path | filename only | safe only under the single-holder assumption that #3 weakly guarantees |
| 5 | stop.bat:3 `taskkill /F /IM python.exe /FI WINDOWTITLE` | no | no | title-substring, not cmdline identity | no | no | no | BROADER THAN PID: image+title force-kill, zero ownership proof; can kill foreign python.exe |
| 6 | status.bat / start.bat / install_service.ps1 | no | no | no | no | no | no | no process-ownership decisions (display / spawn / task registration) |
| 7 | supervisor (`windows_muse_wall/*.py|*.ps1`) | — | — | — | — | — | — | ABSENT ON DISK: cannot verify; persisted slot records carry `owner_token` + `workdir` + null `process`, which proves nothing about live-process checks |

## Every place PID alone is trusted

1. `scripts/windows_worker/daemon.py:260-266` — lock recycle/block decision
   trusts tasklist PID-exists alone (int-parse of lock file at :260, substring
   test at :263). No creation-time, command-line, or parent check exists in
   the worker code (verified by search; `process_create_time` appears ONLY in
   `handoffs/handoff_pid_reuse_lock.json`, an unimplemented fix note).
2. `scripts/windows_worker/daemon.py:213` — `run_id` = PID string, used as the
   run's identity in results without any verification step.
3. Implicit: `stop.bat` trusts LESS than a PID (image + window title) for a
   destructive action — listed here because it is the de-facto STOP ownership
   mechanism and it proves no ownership at all.

## Never used for ownership in Windows worker code

- Creation time: never. Command line: never (title filter is not identity).
- Parent PID: never. Workspace: artifacts only, never process binding.
- Worker ID: lock-filename scope + server registration only, never process
  verification.
