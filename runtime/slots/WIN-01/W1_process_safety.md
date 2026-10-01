# W1 RESULT — Windows process-safety audit (static, read-only)

MODE: shell-less LIGHT. Audited: scripts/windows_worker/daemon.py,
scripts/windows_muse_wall/supervisor.py + slot_state.py + watcher.py,
scripts/agent_session_manager.py, scripts/run_visual_studio_server.py
(process-mgmt surface). Checked against mission invariants. No execution.

## Verified safe (structural)
- Worker daemon: communicate(timeout=600) drains pipes (no deadlock);
  CREATE_NEW_PROCESS_GROUP; cleanup is exact-PID taskkill /F /T (no broad
  kills). PID-reuse SAFE on Windows: our open Popen handle pins the PID.
- Supervisor: NO_STACKING (already_running guard), pid+create_time identity
  (process_matches, 1s tolerance), unknown-ownership blocks stop
  (no_matching_owned_process), terminate->wait(5)->kill->wait(5),
  RUNNING reaped to DONE when process gone (no orphan RUNNING).
- agent_session_manager: cleanup_session validates proc_info
  (start-time+cmdline) BEFORE kill_pid; audit_orphans never kills live;
  kill_pid's only caller is the validated path. PID-safe as a whole.
- run_visual_studio_server.py: zero process-management calls (display only).
- watcher.py: 1Hz display loop, no process control.
- Timeout-finish race resolves FAIL-CLOSED (late finisher reported FAILED;
  server-side retry is bounded) — conservative, acceptable.

## Findings (for owners, not fixed — read-only, no WRITE_SCOPE)
PS-W1-1 (LOW) WORKER NEVER REAPS AFTER TASKKILL.
daemon.py:205-212 kills without wait()/communicate() after. Each timeout
leaks a process handle until GC and returncode stays unknown. Owner: worker.
PS-W1-2 (LOW, KNOWN B1, RE-VERIFIED) SLOTLOCK HAS NO STALE DETECTION.
slot_state.py:16-36 writes pid+timestamp into the lock but never reads it
for staleness; a crash-holder wedges the slot permanently (O_EXCL).
0 stale slot.lock files on disk today. Owner: wall scope.
PS-W1-3 (INFO) STOP_SLOT SECOND WAIT UNCAUGHT.
supervisor.py:216 candidate.wait(timeout=5) after kill can raise
psutil.TimeoutExpired out of stop_slot (SlotLock still released via
context manager). Narrow; zombie-resilient in practice.
PS-W1-4 (INFO) KILL_PID IS A RAW PRIMITIVE.
Safe today (single validated caller); needs a "call only after identity
check" contract comment so future callers don't skip validation.
PS-W1-5 (OK) NO STACKING / NO ORPHAN PATHS FOUND in audited files.

## Safety-invariant mapping
PROCESS_SAFETY: held structurally (exact-PID/tree kills only).
PID-reuse: safe in all 3 paths (handle pinning / create_time / proc_info).
AMBIGUOUS_STARTED_SAFE: timeout->FAILED, server decides bounded retry.
RESULT_READY_NO_REEXEC: markers + result_id idempotency (see MUSE-45 T14).

## Disposition
READ ONLY (no WRITE_SCOPE granted). PS-W1-1..4 to worker/wall owners.
No files outside runtime/slots/WIN-01 touched. No Mac scope touched.
