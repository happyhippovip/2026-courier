# MW3_WINDOWS_RESTART_FIXTURES — deterministic Windows recovery scenarios

MISSION=MW3_WINDOWS_RESTART_FIXTURES MODE=READ_ONLY_PREP DATE=2026-09-26
PREPARED_BY=WIN-06 SESSION=01a0dcac-1002-7e02-bb95-adacfb630c52 SHELL=DOWN
NO_CODE_WRITES (this report + slot claim markers are the only artifacts).

OUTPUT NOTE: requested path `C:\Users\lol\courier_work\reports\...` is OUTSIDE
this session's writable roots (workspace root, runtime temp, /tmp only), so the
canonical artifact lives here: `runtime/slots/WIN-06/MW3_WINDOWS_RESTART_FIXTURES.md`.
Operator copies it to the requested path (`/tmp` mirror attempted, denied:
path escapes workspace — write tool is workspace-only).

GROUNDING LEGEND: OBSERVED = read by me this session (daemon.py 1-403,
stop_safe.py 1-109, worker_status.py 1-101, server/app.py claim head 720-812,
slot/job/log artifacts, wall .ps1). PEER-OBSERVED = read by WIN/MUSE-45 peers
today, cited, not re-read by me. UNVERIFIED = needs shell/machine.

TREE ANOMALY (limits S2 grounding): `scripts/windows_muse_wall/*.py`
(supervisor.py, __init__.py, watcher.py, slot_state.py) return OS "not found"
on direct read, while same-dir .ps1 + config.json read fine and peers read
supervisor.py content today (active-writer tree mutation suspected; no git to
confirm). S2 code rows are PEER-OBSERVED; re-verify on tree settle.
`tests/test_restart_resume_torture.py` likewise unreadable (see MUSE-45 T-G).

STAGING (all scenarios): fixed task ids FIX-01.., markers under
`scripts/windows_worker/state/`, lock `%TEMP%\courier_worker_<id>.lock`;
runner records PID + create_time + file bytes at each step (shell required;
fixtures here are SPECS, no scripts written per READ_ONLY_PREP).

---

## S1 — worker process dies (SIGKILL mid-task, no cleanup)

STAGE: start daemon, claim FIX-01 (long powershell sleep), SIGKILL daemon PID
mid-effect. Restart daemon, observe recovery.

EXPECTED_SAFE_STATE=
lock stale on disk; effect_marker.json present (died during effect) and/or
result_marker.json present (died after persist, before/during post); restart
runs recover_pending_markers BEFORE any new claim; ambiguous effect resolves to
FAILED/AMBIGUOUS_CRASH post (never replayed); saved result reposted
byte-identical then unlinked; server task stays DISPATCHED under same worker
(reclaim path re-returns it, no duplicate dispatch).

FORBIDDEN_ACTION=
re-executing the recorded effect; deleting either marker before server ACK;
starting a second daemon instance (O_EXCL lock + stale-check gate must hold);
broad taskkill to "clean up"; unlinking effect marker when NOT same_execution.

EVIDENCE_REQUIRED=
effect/result marker bytes (goal/task/attempt/dispatch/execution_ref);
lock bytes; restart log lines (ambiguous-crash post OR result repost + unlink);
server ACK / ACK_DUPLICATE response; exactly one reconciled result server-side;
zero duplicate external effects.

## S2 — supervisor restarts (wall init/admit/status cycle)

STAGE: snapshot all 64 state.json + 16 job.json + log line counts; restart
supervisor flow (init/admit/status per start_all.ps1); re-snapshot; diff.
GROUNDING: artifacts OBSERVED; supervisor code PEER-OBSERVED (MUSE-%02d
addressing, init/admit/status verbs, run_job append "ab" logs, MUSE-45 T-A).

EXPECTED_SAFE_STATE=
state.json files are durable truth: DONE stays DONE (zero DONE->READY flips),
READY stays READY; re-init idempotent; admit honors config active_limit;
job.json finished_at/status preserved; log line counts monotonic non-decreasing
(append-only); single wall generation (no duplicate titles/hosts).

FORBIDDEN_ACTION=
re-queueing DONE jobs on restart; resetting owner_token/admissions; launching
a second wall generation while one is open; overwriting (vs appending) job logs.

EVIDENCE_REQUIRED=
pre/post dumps of 64 state.json + 16 job.json with empty-flip diff;
per-slot log line counts before/after (monotonic); admit/status outputs;
wall process census (one generation).

## S3 — RESULT persisted but ACK lost (post ok server-side, response lost)

STAGE: run task to result persist; sever response path (kill -9 between post
return and marker unlink, or drop ACK); restart; observe repost.

EXPECTED_SAFE_STATE=
result_marker.json still present at restart; repost payload IDENTICAL to saved
bytes (same task/attempt/dispatch/execution_ref AND same result_id — daemon
reuses saved payload, mints fresh ids only for new results); server answers
ACK_DUPLICATE (or accepts once); marker unlinked only after ACK; effect marker
unlinked only if same_execution(effect, saved_result).

FORBIDDEN_ACTION=
recomputing the result by re-running the task; minting a NEW result_id for the
same execution (contradictory-duplicate shape); unlinking the marker pre-ACK;
posting AMBIGUOUS_CRASH when a complete result is on disk.

EVIDENCE_REQUIRED=
saved marker bytes vs reposted payload (identical modulo transport framing);
server ACK_DUPLICATE/accept response; single reconciled result server-side;
marker absent only after ACK; no second task execution in logs.

## S4 — stale structured lock (daemon dead, JSON pid+create_time lock remains)

STAGE: write structured lock {pid: dead PID, process_create_time: T};
run acquire path (daemon start) and stop path (stop_safe) separately.

EXPECTED_SAFE_STATE=
acquire: stale detected (pid dead OR |actual-expected create_time| > 1.0s),
lock unlinked, lock re-acquired (recursive acquire returns path, single owner);
stop: same check, stale lock cleaned, nothing signalled, exit non-zero with
"no longer exists"/"reused" message; worker_status daemon_running=false.
(KNOWN DEVIATION: worker_status checks pid_exists only, no create_time —
may false-positive; see W02-01 peer audit + this report S5.)

FORBIDDEN_ACTION=
killing the recorded PID without create_time verification; deleting a
NON-stale lock (live owner verified); starting a duplicate daemon bypassing
O_EXCL; treating lock presence alone as liveness.

EVIDENCE_REQUIRED=
lock bytes before/after; pid_exists + create_time readings at check time;
acquire result (path vs None); process census (exactly one owner); stop_safe
stdout ("reused by different process. Cleaning stale lock." where applicable).

## S5 — PID reused (lock PID now belongs to unrelated live process)

STAGE: plant unrelated sleeper process P (record its create_time Tc);
write lock referencing P.pid with expected create_time Te != Tc (structured)
— and separately a plain-PID lock with P.pid. Run stop path, then acquire path.

EXPECTED_SAFE_STATE=
structured lock: create_time mismatch -> stale -> lock cleaned, ZERO signals
to P (P alive after, same Tc); plain-PID lock: EXPECTED same (no kill).
DOCUMENTED CURRENT-CODE DEVIATION (static, OBSERVED): daemon writes plain-PID
locks (daemon.py:288) so stop_safe takes the create_time=None path and WOULD
terminate P (fail-open; RESULT_01 F1/F2); acquire path fails closed (refuses
start, safe direction). Fixture asserts the SAFE expectation; run against
current code must record this as KNOWN-FAIL until owner fix.

FORBIDDEN_ACTION=
terminate/kill/wait on PID-identity alone; children-tree kill rooted at an
unverified PID; assuming lock PID == daemon without create_time proof.

EVIDENCE_REQUIRED=
P alive post-run with unchanged Tc; lock cleaned (structured case);
kill-audit (no terminate/kill syscalls against P.pid; stop log captured);
plain-PID case verdict recorded as KNOWN-FAIL with code refs, not PASS.

## S6 — child process survives parent (orphaned task child outlives daemon)

STAGE: start daemon task spawning powershell child C (+ grandchild G);
SIGKILL daemon (finally/taskkill never runs); snapshot tree; run exact-tree
recovery (children of recorded run PID); snapshot again. Reboot variant:
reboot with orphans recorded; recover post-boot.

EXPECTED_SAFE_STATE=
orphans attributable via recorded run_id (= task powershell PID) + children
enumeration; exact-tree cleanup terminates C+G (taskkill /F /T /PID on
verified pids, or psutil children-recursive of verified parent); unrelated
same-name processes (other powershell/python) untouched; reboot variant: pids
re-validated by create_time/parent-chain before any signal (PIDs recycle
across boot); stop_all_slots semantics (per-slot exact stop, tracked jobs
only — PEER-OBSERVED, AUTO_starter_review).

FORBIDDEN_ACTION=
broad kills by process name (taskkill /IM powershell.exe, pkill python, ...);
killing by PID without create_time/parent verification (especially post-boot);
assuming children died with parent (no-check skip).

EVIDENCE_REQUIRED=
pre/post process-tree snapshots (pids + names + create_times + parents);
run_id linkage (task record -> PID); census proof: exact pids gone AND
unrelated same-name pids alive; procedure contains zero by-name kill commands.

---

## Determinism checklist (runner enforces; shell required)

FIX task ids; fixed worker id; clean state dir per run (markers/locks removed,
bytes archived); recorded (pid, create_time) at every step; server state export
before/after (tasks/workers snapshots); PASS = all EXPECTED rows hold + all
EVIDENCE rows captured + zero FORBIDDEN actions in logs; S5-plain-PID is
KNOWN-FAIL until fixed (do not greenwash).
Related: WIN-06 RESULT_01 (slot plumbing verify), MUSE-45 T-G (restart/queue
coverage), T-A (staged scaling), W02-01 (stop audit), AUTO_starter_review.
