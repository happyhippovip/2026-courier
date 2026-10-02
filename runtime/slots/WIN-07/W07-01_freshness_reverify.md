# W07-01 RESULT — freshness re-verification after checkout switch (read-only)

MODE: shell-less LIGHT. Ground truth via .git reads (T22/H2-1 method).
SCOPE: my ex-WIN-02 findings (W02-01 SS-1..SS-7/WS-1, W02-02 SK-1..SK-4)
re-resolved against the CURRENT checkout. No peer-inventory duplication
(WIN-06 HARVEST_01/02 + MUSE45 T-L1/T-L2 own the switch inventory; incident
packet MUSE45_INCIDENT_branch-switch exists).

## Checkout ground truth (OBSERVED, first git identity in this session)
BRANCH=fix-cb1-new (.git/HEAD) @ SHA 329abd8077a9f53ecd34eb3bee5d506735d06dbe
(loose ref). Corroborates WIN-06 H2-1. Pre-switch line was
ledger-reconciliation-final @ b927f106 (per HARVEST_02; old loose ref deleted).
ALL W02-01/W02-02 line citations are OLD-REV scoped (b927f106-era tree).

## Absence verdicts (OBSERVED: read_file os-error-2 + zero code-side hits)
- stop_safe.py ABSENT ("No lock file found": 0 hits repo-wide).
- worker_status.py ABSENT ("Daemon Running:": only my own report).
- soak_test.py ABSENT ("Starting soak test": 0 hits).
- supervisor.py ABSENT ("class MuseWallSupervisor", "slot_job_mismatch",
  "test_job_snippet": 0 code hits; corroborates WIN-06 H2-4).
- run_loop.bat/start.py absent per T-L2 packet (not independently re-probed;
  stop.bat no longer references run_loop).
Present + rewritten: daemon.py (msvcrt lock, :263-275), stop.bat (title
filter, :3). Present: .git/HEAD + loose ref. Untracked slot reports persist.

## Finding re-verdicts
SS-1 (was MEDIUM): ROOT-CAUSE LINE PERSISTS, HAZARD MOOT on fix-cb1-new.
daemon.py:271 still writes plain-PID. BUT no code reads lock content anymore:
stop_safe.py gone, daemon's stale-parse path deleted with the O_EXCL design
(new acquire_lock :263-275 never reads the file; contention -> msvcrt
OSError -> exit 0, NO_STACKING holds, arguably stronger). Residual risk only
if an operator hand-reads the stale PID. Handoff filing
handoffs/handoff_pid_reuse_lock.json (HIGH, WRITE_SCOPE daemon.py) exists and
owns the fix — but its REPRO step 4 ("tricking acquire_lock") is now STALE:
new acquire_lock cannot be tricked by file content. Handoff owner: update or
re-scope. If ledger line restored, SS-1 REVIVES as filed (file-gated).
SS-2/SS-3/SS-4/WS-1/SS-5/SS-6: OLD-REV (host files absent). Preserved for
ledger line; nothing to re-verify on fix-cb1-new.
SS-7 (stop.bat): REWRITTEN, re-verdict N3 (LOW-MEDIUM, NEW TREE): :3 is now
`taskkill /F /T /IM python.exe /FI "WINDOWTITLE eq CourierWindowsWorker*"`.
Narrower than the CIM cmdline-substring (packet-F3's editor/grep/mac-worker
hazard GONE — improvement) BUT success-unverified: always echoes "Stopped.",
exit 0, no check. Title-dependent: daemon windows not titled
CourierWindowsWorker* are silently missed (likely no-op); coincidental title
matches still multi-kill. Worst case bounded by msvcrt start-refusal (no
stacking), so operator-confusion class, not safety class. Owner: worker scope.
SK-1..SK-4: OLD-REV (soak_test.py + supervisor.py absent). SK-2's "do not run
at repo root" warning is moot while the file is absent; REVIVES if ledger
restored. Nothing to re-verify on fix-cb1-new.
N1 (LOW, INFERRED-not-observed, NEW TREE): finally at daemon.py:380-382 does
os.remove(lock_path) while _lock_fd is still OPEN (:272, never closed/
unlocked). On Windows, deleting a file with an open non-SHARE_DELETE handle
fails (PermissionError) -> clean daemon exit likely ends in a finally
traceback. REGRESSION vs old tree (fd closed at write). Needs execution to
confirm; owner: worker scope. (Fix sketch, NOT applied: close/unlock fd
before remove, or wrap remove in try.)
N2 (INFO, NEW TREE, corroborated-good): rewritten phase machine looks sound:
interrupted STARTED released, never replayed (:304-308, AMBIGUOUS_STARTED_SAFE
holds); RESULT_READY kept for redelivery (:354-355, RESULT_READY_NO_REEXEC
direction); REJECTED persisted as RELEASE_PENDING before release (:361-362,
crash-safe ordering). Spot read only, not a full audit.

## Peer cross-check (ladder #1, no re-work)
WIN-03 W5_verify_peers independently CONFIRMED SS-1..SS-4 on the old tree
(V5-5/V5-6 exact, 7-line drift noted) before the switch. My old-rev findings
stand as filed for the ledger line. T20 re-confirmed 3 MUSE-45 findings as
STILL OPEN pre-switch. No contradictions found anywhere this pass.

## Safety-invariant mapping (fix-cb1-new, daemon only)
NO_STACKING: held (msvcrt LK_NBLCK, fail-closed exit). PROCESS_SAFETY: daemon
task path not re-audited this pass; stop path narrowed (N3). PID-reuse: no
code actor consumes PIDs from files (hazard moot). AMBIGUOUS_STARTED_SAFE +
RESULT_READY_NO_REEXEC: structurally sound in spot read (N2).

## Disposition
READ ONLY (WRITE_SCOPE=NONE). N1+N3 to worker owner; handoff-step-4 staleness
to handoff owner; canonical-checkout question (HARVEST_02 input-1) REMAINS
OPEN and blocks all "current" citations beyond this SHA-pinned report.
No files outside runtime/slots/WIN-07 (+ prior WIN-02 vacate note) touched.
No Mac scope touched.

## RESULT
BRANCH=fix-cb1-new
SHA=329abd8077a9f53ecd34eb3bee5d506735d06dbe
TASK=W07-01 freshness re-verification of W02 findings post-switch
WRITE_SCOPE=NONE
FILES_CHANGED=3 (runtime/slots/WIN-07/state.json, CLAIM.md, W07-01_freshness_reverify.md)
TEST_COMMAND=none (shell down; static read/search only)
TESTS_PASSED=n/a
TESTS_FAILED=n/a
FAILED_TEST_NAMES=n/a
ARTIFACT=runtime/slots/WIN-07/W07-01_freshness_reverify.md (this file)
RESULT_STATE=COMPLETE (4 absent-host verdicts, SS-1 re-scoped, N1+N3 new, N2 info)
