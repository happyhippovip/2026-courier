# W04-T7 RESULT — Worker service restart loop (static, read-only)

> CANONICAL COPY. First written as W03-T7 under runtime/slots/WIN-03/; that
> slot was contested by live peer 01a0dcbf-8a15 and vacated by this session
> (see ../WIN-04/CLAIM.md collision note). WIN-03 copy: stale, do not use.
> SESSION=01a0dcac-1051-7622-96e9-d9d532bdbd49.

Files: scripts/windows_worker/run_loop.bat, install_service.ps1, daemon.py
loop() (:330-403). No edits (worker/installer scope; Google writer active).

## Observed wiring
- run_loop.bat: infinite `uv run python -u daemon.py >> logs\worker.log`,
  fixed 5s pause, no exit, no counter, no backoff.
- daemon loop() itself: error backoff 10s->300s (:344-345,391-393), idle
  backoff 5s->30s (:347-348,388,396), resource gate pauses claims (:365-368),
  lock released in finally (:398-400). Inner loop GOOD.
- install_service.ps1: ScheduledTask CourierWindowsWorker, AtLogon +
  Interactive current user, NO -Settings (no interval, no recovery, no limit).

## Findings (owner triage)
W04-T7-1 (P2) OUTER LOOP HAS NO CRASH BACKOFF (inner loop does).
Daemon FATAL paths (e.g. missing API key :26-29 sys.exit(1), unhandled loop
bug) restart every 5s FOREVER: hot crash-loop + log spam + CPU churn, no
crash counter, no circuit breaker, no alert hook. Contrast: inner backoffs
are exemplary. Suggest crash-count file + growing delay, or Task recovery
settings (see T7-2). Testable with shell (exit-1 stub).

W04-T7-2 (P2, INFERRED — one shell probe settles it) NO TASK RECOVERY/LIMIT
SETTINGS. Register-ScheduledTask without -Settings inherits platform
defaults: ExecutionTimeLimit default (commonly 72h) would SILENTLY KILL a
healthy long-running worker; no RestartOnFailure/RestartCount. Settle with:
task XML dump (schtasks /query /tn CourierWindowsWorker /xml) on a live box.
Complements RESTART_recovery R-1 (nonzero-exit semantics; theirs, cited).

W04-T7-3 (P3/INFO) `uv run` IN THE UNATTENDED SERVICE PATH.
Implicit sync/resolve on EVERY (re)start: offline fragility + lockfile-churn
surprises for a service that must survive reboots quietly. Suggest pinned
python via .venv_service (consistent with T8 motor path) — owner call. Same
interpreter-pinning family as DISPATCHER G-5 (different file, cited).

## Explicit non-dup (theirs, cited)
- Unbounded worker.log append: PORTABILITY P-5 (theirs).
- AtLogon-not-boot + "start on boot" message: T8 F-T8-2 (theirs).
- Bootstrap handshake strings: T8 F-T8-5 OK (theirs).
- Server crash corners (exit-0/truncation/batch): RESTART_recovery R-1..R-3.
- Google queued "restart recovery live test" + "daemon auto-start eval"
  (checkpoint Next 3-4): owner TEST scope with shell; these static notes are
  inputs, not competition — no test files written here.

BRANCH=ledger-reconciliation-final (per checkpoint; git unverified). SHA=
UNKNOWN (no git). FILES_CHANGED=0 (outside own slot). TESTS 0/0 (shell down).
RESULT_STATE=STATIC_FINDINGS_PARKED.
