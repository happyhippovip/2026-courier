# W02-01 RESULT — stop_safe / worker_status / stop.bat static audit (read-only)

MODE: shell-less LIGHT. No execution, no edits outside runtime/slots/WIN-02/.
Audited (full reads): scripts/windows_worker/stop_safe.py (109 lines),
scripts/windows_worker/worker_status.py (101 lines),
scripts/windows_worker/stop.bat (4 lines), daemon.py lock path (283-328),
tests/test_windows_daemon_completeness.py TestSafeStop (191-215).
Overlap-checked: WIN-01 W1 (did NOT cover these files), MUSE-45 T8 (no
stop.bat mention), ops packet MUSE45_T-B (F3 owns stop.bat broad-kill).

## Verified safe (structural)
- stop_safe.py: lock-file PID targeting, no process-name/CmdLine matching
  (no process_iter, no name match). NoSuchProcess -> cleans stale lock, no
  kill (63-67). Unreadable lock -> return False, no action (56-59).
  terminate -> wait(10) -> kill -> wait(5) escalation (83-88).
- worker_status.py: genuinely read-only (zero writes/kills/mutations);
  broad-except reports False/UNREADABLE, never crashes (52-53, 62-63, 82).
- daemon.py AccessDenied on create_time -> stale=False, refuses start
  (318-319): fail-CLOSED for start. NO_STACKING held.

## Findings (for owners, NOT fixed — WRITE_SCOPE=NONE)
SS-1 (MEDIUM, NEW) IDENTITY CHECK IS DEAD IN PRACTICE — PLAIN-PID LOCKS.
stop_safe.py:3-4 documents "verifies process identity (PID + create_time)",
but the check at :69 runs ONLY when the lock carries create_time, and
daemon.py:288 ALWAYS writes plain-PID locks (`os.write(fd,
str(os.getpid()))`). Production stop path = PID-only kill, zero reuse
protection. Scenario: hard-killed daemon leaves stale plain-PID lock
(finally at daemon.py:398 never runs on hard kill) -> OS reuses PID ->
operator runs stop -> UNRELATED PROCESS TREE terminated. Consequence is
arbitrary tree-kill; probability per event low (exact-PID reuse + manual
stop). Companion: daemon acquire_lock has the same gap (:306 pid_exists
only for plain-PID) -> refuses restart while real owner dead (fail-closed
direction: safe, but worker stays down until manual lock delete).
CORRECTION to packet F3's recommendation: routing stop through stop_safe.py
does NOT buy PID+create_time safety until the daemon WRITES structured
locks {pid, process_create_time} at acquire. Owner: worker scope.
SS-2 (LOW, NEW) ACCESSDENIED FAILS OPEN (stop) vs FAILS CLOSED (start).
stop_safe.py:76-77: if create_time() raises AccessDenied (elevated/other-user
process in PID), code falls THROUGH to terminate an identity-UNVERIFIED
process. daemon.py:319 treats the same signal as stale=False (refuse).
Same signal, opposite directions. Narrow (same-user daemons rarely hit),
but the unsafe direction. Owner: worker scope.
SS-3 (LOW, NEW) CHILDREN CLEANUP TERMINATE-ONLY + REUSE RACE.
stop_safe.py:82 snapshots children pre-terminate, then :91-96 terminate()
leftovers with no wait, no kill escalation, no identity re-check. A
fast-exiting child PID reused between snapshot and terminate() gets an
unintended signal; a terminate-ignoring child survives as orphan. Narrow.
Owner: worker scope.
SS-4 (LOW, NEW) POST-KILL WAIT UNCAUGHT -> STALE LOCK LEFT.
stop_safe.py:88 proc.wait(timeout=5) after kill can raise
psutil.TimeoutExpired out of stop_worker (only NoSuchProcess caught, :97) ->
:101 unlink skipped, traceback, exit 1, stale lock remains. Same family as
WIN-01 PS-W1-3 (supervisor). Owner: worker scope.
WS-1 (LOW, NEW) STATUS CAN REPORT FALSE-ALIVE AFTER PID REUSE.
worker_status.py:51 daemon_running = psutil.pid_exists(pid), no create_time
check even when the lock HAS structured metadata (:48-49 parses pid only).
Stale lock + reused PID -> "Daemon Running: True" for a stranger. Read-only
(no destructive effect) but can fool operator/automation into skipping a
needed restart. Owner: worker scope.
SS-5 (INFO) TOCTOU UNLINK on stale-lock cleanup (:66, :74): lock re-read is
not re-verified before unlink; a daemon that restarted between read and
unlink loses its FRESH lock. Narrow race. Owner: worker scope.
SS-6 (INFO) `import os` at stop_safe.py:7 unused (zero os.* uses). Cosmetic.
SS-7 (CORROBORATED, packet F3 owns) stop.bat:3 IS a broad kill
(Get-CimInstance ... CommandLine -match 'daemon.py|run_loop.bat' |
Terminate): matches editors, greps, other checkouts, mac_worker daemons.
Repo-wide "stop.bat" refs: ONLY packet + checkpoint + test (OBSERVED) ->
NOT wired into any installer/launcher; present and one-double-click away.
CORRECTION to packet F3 "stop_safe.py ... is tested": TestSafeStop pins
ONLY presence/string-content (importable, "lock" substring, no broad-match
substrings, :194-215). ZERO behavioral tests: create_time verify, plain-PID
skip, AccessDenied path, post-kill wait all unpinned. Owner: worker scope.

## Safety-invariant mapping
PROCESS_SAFETY: stop_safe structurally exact-PID (no broad matching) BUT
PID-reuse protection DOCUMENTED-yet-ABSENT for daemon-written locks (SS-1).
PID reuse: UNSAFE in stop path (plain-PID, unverified); safe direction only
in daemon start-refusal (availability cost). STOP_DURABLE: SS-4 can leave
stale lock on kill-timeout. AMBIGUOUS_STARTED_SAFE: n/a here. NO_STACKING:
held (O_EXCL + pid_exists refusal). RESULT_PERSISTENCE_SAFE: n/a here.

## Disposition
READ ONLY (no WRITE_SCOPE granted). SS-1..SS-7 + WS-1 to worker owner.
Suggested owner order: (1) daemon writes structured locks (activates
existing checks in BOTH files, kills SS-1 + WS-1 root cause); (2) AccessDenied
-> refuse with message (SS-2); (3) catch TimeoutExpired around :88 + always
unlink (SS-4); (4) wire operational stop through stop_safe.py (packet F3)
AFTER (1), else the rewire is safety theater; (5) pin behavior with tests.
No files outside runtime/slots/WIN-02 touched. No Mac scope touched.

## RESULT
BRANCH=UNKNOWN (shell down, no git)
SHA=UNKNOWN (shell down; Google checkpoint reports HEAD 27b22d7... UNVERIFIED here)
TASK=W02-01 stop_safe/worker_status/stop.bat static audit
WRITE_SCOPE=NONE
FILES_CHANGED=2 (runtime/slots/WIN-02/CLAIM.md, runtime/slots/WIN-02/W02-01_stop_safe_audit.md)
TEST_COMMAND=none (shell down; static read-only audit)
TESTS_PASSED=n/a
TESTS_FAILED=n/a
FAILED_TEST_NAMES=n/a
ARTIFACT=runtime/slots/WIN-02/W02-01_stop_safe_audit.md (this file)
RESULT_STATE=COMPLETE_STATIC_FINDINGS (1 MEDIUM, 3 LOW, 3 INFO+corroboration)
