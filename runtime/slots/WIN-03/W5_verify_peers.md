# W5 RESULT — Verify existing results (ladder #1; static, read-only)

MODE: shell-less LIGHT. Independent third-party verification of peer claims
(WIN-01 W2, WIN-02 RESULT_01/W02-01/W02-02, MUSE-45 T18 vs VERIFY). Method:
fresh reads of cited code/log/config lines — never trust, always re-open.
No execution. Peer files untouched.

## Verdicts (14 checked, 14 CONFIRMED, 0 contradicted)
V5-1 CONFIRMED: 16/16 job logs exist (runtime/slots/MUSE-NN/logs/job-JOB-NN.log
contain JOB markers). MUSE-45 VERIFY "absent" correctly SUPERSEDED by T18.
V5-2 CONFIRMED (independent spot sample): MUSE-02 log = 3x `JOB-02 on MUSE-02 OK`,
MUSE-05 log = 2x `JOB-05 on MUSE-05 OK` — exact T18/WIN-02 census prediction on
slots neither sampled before. Staged-append model (supervisor "ab") holds.
V5-3 CONFIRMED: config.json active_limit=16, provider_launch_enabled=false →
Google checkpoint's claimed "false→true" edit NOT present in current tree
(WIN-02 CONTRADICTED verdict stands; read-only observed, file untouched).
V5-4 CONFIRMED: daemon writes PLAIN-PID locks (daemon.py:294-295 O_EXCL +
str(getpid); WIN-02 cited :288 — 7-line drift, content exact). SS-1/F2
linchpin holds: stop_safe.py:69 check skipped when create_time None.
V5-5 CONFIRMED: stop_safe.py:76-77 fail-OPEN (NoSuchProcess+AccessDenied → pass
→ falls through to terminate) vs daemon.py:318-319 fail-CLOSED. SS-2/F1 exact.
V5-6 CONFIRMED: stop_safe.py:90-96 children terminate-only (no wait/kill/
re-check) → SS-3 exact. :88 post-kill wait uncaught (only NoSuchProcess at
:97) → SS-4 exact.
V5-7 CONFIRMED: worker_status.py:51 pid_exists-only; :48-49 parses structured
pid but ignores create_time → WS-1 false-alive exact.
V5-8 CONFIRMED: uninstall.ps1:31 broad CIM kill (CommandLine -match
"daemon.py|start.bat" | Terminate) → WIN-01 PS-W2-1 exact. :35 self-delete
under -RemoveData + SilentlyContinue → PS-W2-2 exact. (Invoke-CimMethod is
not Invoke-Expression — consistent with W2's zero-IEX claim.)
V5-9 CONFIRMED (all four): soak_test.py:8 repo-root runtime, :13/:30 in-memory
gate flips, :16-18 live MUSE-01..03 starts, :44 unconditional "success",
~12s wall time, unchecked stops → SK-1/SK-2/SK-3/SK-4 exact. SK-2 (DONE→READY
rewrite of proof slots) is the sharpest live-state hazard in the wall tree;
re-affirmed: DO NOT RUN against repo root while proof matters.

## New notes (mine)
N5-1 (INFO) WIN-01/CHECKPOINT.md line 3 claims "only WIN slot on disk" — stale
since WIN-02/WIN-03 exist. Their file; flagged here, not touched.
N5-2 (INFO) Line-drift watch: peer line pins drift ~7 lines (daemon :288→294).
Content exact everywhere; future pins should cite function names + lines.

## Evidence (mission RESULTS format)
BRANCH=ledger-reconciliation-final (.git/HEAD, re-read prior turn)
SHA=UNKNOWN this session (no shell; last documented 27b22d7e, Google 07:45)
TASK=W5 verify existing results (ladder #1)
WRITE_SCOPE=NONE
FILES_CHANGED=0 repo files (own-slot artifacts only)
TEST_COMMAND=none (shell runner DOWN)
TESTS_PASSED=0 / TESTS_FAILED=0 (none run; static verification only)
FAILED_TEST_NAMES=none
ARTIFACT=runtime/slots/WIN-03/W5_verify_peers.md
RESULT_STATE=ANALYSIS_COMPLETE

## Disposition
READ ONLY. No new defect filings — all findings already owned by WIN-01/WIN-02
reports (corroborated, not duplicated). No files outside runtime/slots/WIN-03
touched. No Mac scope touched. No peer slots touched.
