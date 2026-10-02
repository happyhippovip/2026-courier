# W02-02 RESULT — wall soak_test.py static review (read-only)

MODE: shell-less LIGHT. No execution, no edits outside runtime/slots/WIN-02/.
Audited (full reads): scripts/windows_muse_wall/soak_test.py (47 lines),
supervisor.py start_slot :172-198 + stop_slot :200-220 (transition proof).
Overlap-checked: T10/T11 mention soak_test.py as INVENTORY ONLY (0-test
collectable file); no behavioral review anywhere. NEW.

## What it does
Repo-root runtime -> init -> in-memory provider_launch_enabled=True ->
start MUSE-01..03 with `python -c "import time; time.sleep(10)"` -> sleep 2
-> stop MUSE-02 -> new supervisor instance ("restart") -> reconcile 3 slots
-> print status -> stop rest -> print "completed successfully". No asserts,
no exit-code discipline, no isolated runtime, no state restore.

## Verified safe (structural)
- Payload self-bounding: sleep(10), no infinite loop, no busy loop.
- Uses exact supervisor APIs (start/stop/reconcile under SlotLock), no raw
  kills, no broad matching.
- Exercises a REAL path: restart -> reconcile -> status -> stop.

## Findings (for owners, NOT fixed — WRITE_SCOPE=NONE)
SK-1 (MEDIUM-LOW, NEW) CANNOT FAIL — "SUCCESS" IS UNCONDITIONAL.
Every result dict is printed (:19, :37) or DISCARDED (:25 stop, :34
reconcile, :42 stops). already_running / provider_launch_disabled /
no_matching_owned_process / CRASHED transitions all still end at :44
"Soak test completed successfully." with exit 0. Only an uncaught exception
goes red. As a regression gate over PROCESS_SAFETY paths this is safety
theater. Owner: wall scope. Suggested: assert each res flag + final states,
sys.exit(nonzero) on any deviation.
SK-2 (MEDIUM, NEW) REWRITES LIVE PROOF STATE: DONE -> IDLE -> READY.
:8 roots at the REPO (parent x3), i.e. canonical runtime/slots, NOT a temp
copy. start_slot sets slot["state"]="IDLE" + live PID entry (supervisor.py
:191-197); stop_slot sets "READY" (:217-219). One run therefore flips
MUSE-01..03 out of DONE — the exact slots Google's staged proof
(JOB-01..16 -> DONE, checkpoint 2026-09-26T07:45) banks on — permanently
rewriting 3 proof records to READY. No backup/restore, no lock/coordination
with the live wall or the Google writer scope, no --dry-run. This script IS
an uncoordinated writer. Until fenced, DO NOT RUN against repo root while
any proof state matters. Owner: wall scope. Suggested: temp-runtime root
(argv/env override) + restore, or explicit --live flag with refuse-default.
SK-3 (LOW, NEW) "SOAK" MISNOMER — ~12s, NO SOAK PROPERTIES.
Total wall time ~12s (one sleep(2) + bounded sleep(10) payloads), single
pass, no iteration, no leak/FD/handle accounting, no sustained load. The
user morning flow's 10-15 min soak is unrelated to this file. Name invites
false confidence ("soak passed"). Owner: wall scope. Suggested: rename to
restart_smoke.py or grow real soak properties.
SK-4 (LOW, NEW) IN-MEMORY GATE FLIP + UNCHECKED STOPS.
:13/:30 set provider_launch_enabled=True in-memory (bypasses the config-file
default-deny for this process — legitimate for a test, but combined with
SK-2 it launches REAL processes against LIVE slots). Stop/reconcile results
unchecked: under live-wall lock contention a failed stop leaks a live PID
into a slot the script believes stopped; leakage bounded only by sleep(10).
Owner: wall scope.

## Safety-invariant mapping
PROCESS_SAFETY: held WITHIN the script (exact APIs, bounded payload) but the
script VIOLATES writer coordination (uncoordinated live-state rewrite,
SK-2). STOP_DURABLE: stop outcomes unchecked (SK-4). RESULT_READY_NO_REEXEC:
n/a (no jobs used). NO_STACKING: relies on supervisor guards; script adds
none. Exact-process ownership: inherited from supervisor, sound.

## Disposition
READ ONLY (no WRITE_SCOPE granted). SK-1..SK-4 to wall owner. Highest value:
SK-2 fence (temp-runtime default) BEFORE anyone runs this during proof
season; SK-1 asserts to make it a real gate.
No files outside runtime/slots/WIN-02 touched. No Mac scope touched.

## RESULT
BRANCH=UNKNOWN (shell down, no git)
SHA=UNKNOWN (shell down; Google checkpoint reports HEAD 27b22d7... UNVERIFIED here)
TASK=W02-02 wall soak_test.py static review
WRITE_SCOPE=NONE
FILES_CHANGED=2 (runtime/slots/WIN-02/W02-02_soak_review.md + CLAIM.md log)
TEST_COMMAND=none (shell down; static read-only audit)
TESTS_PASSED=n/a
TESTS_FAILED=n/a
FAILED_TEST_NAMES=n/a
ARTIFACT=runtime/slots/WIN-02/W02-02_soak_review.md (this file)
RESULT_STATE=COMPLETE_STATIC_FINDINGS (1 MEDIUM, 1 MEDIUM-LOW, 2 LOW)
