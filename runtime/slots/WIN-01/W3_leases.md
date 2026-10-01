# W3 RESULT — Worker lease/heartbeat audit (static, read-only)

MODE: shell-less LIGHT. Server lease paths (P3, read-only) + Windows/Mac
daemon loops. Production evidence: logs/courier_daemon.log shows
POST /tasks/reclaim_stale every 60s (live enforcement). No execution.

## Verified sound
- Register: wrong-SHA rejected 426; restart-with-amnesia quarantines the
  server-side task to HUMAN_REQUIRED/WORKER_RESTARTED_AND_LOST_STATE (no
  blind replay); capability/provider metadata validated.
- Heartbeat self-heals: clears worker current_task + frees worker when the
  task left DISPATCHED; unknown worker 404 -> daemon re-registers.
- Claim WORKER_BUSY prevents double-claim stacking.

## Findings (for owners — read-only, no WRITE_SCOPE)
L-W3-1 (MEDIUM) EXECUTION ENVELOPE EXCEEDS STALE THRESHOLD.
Windows daemon heartbeats ONLY at loop top; run_task blocks heartbeats up
to communicate(timeout=600). Reclaim runs every 60s with a 300s threshold
(T14). Any task executing >300s: worker marked stale mid-execution ->
task forced HUMAN_REQUIRED/STALE_WORKER_EFFECT_AMBIGUOUS -> the worker's
result POST then 409s (T12: only DISPATCHED accepts results) -> result
orphaned in local result_marker (resends 409 too) -> human resume with an
ambiguous effect. Healthy long tasks are punitively quarantined.
Fix directions (owner): heartbeat thread during execution, threshold >
envelope, or lease-duration extension on claim. Owner: worker+server scope.

L-W3-2 (LOW) MAC HAS THE SAME PATTERN AT THE BOUNDARY.
Mac daemon: loop-top heartbeat, execution communicate(timeout=300) ==
threshold 300s -> ~5min tasks race the reaper. Noted for the Mac owner
(this mission is Windows-only; no Mac change proposed here).

L-W3-3 (INFO) UNREGISTER KEEPS THE TASK LEASE.
Unregister sets available=False but leaves current_task; last_seen ages ->
reclaim quarantines to HUMAN_REQUIRED. Fail-closed and safe, but graceful
shutdown still costs a human review; could explicitly release the task.

## Disposition
READ ONLY. L-W3-1..3 to worker/server owners.
No files outside runtime/slots/WIN-01 touched.
