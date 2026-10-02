# RESTART/RECOVERY REVIEW — server save path + waitress crash path (static)

Files: server/app.py, server/run_waitress.py (both P3/installer scope).
READ-ONLY: no edits made or proposed as my action; owner triage only.

## R-1 (MEDIUM) Crashed server exits 0 — no auto-restart triggers
run_waitress.py:14-15: `except BaseException` writes the traceback and falls
off the end => process exit code 0 after ANY crash (incl. real exceptions).
Restart-on-failure (Scheduled Task RestartCount / service recovery) triggers
on NONZERO exit; a logged crash looks like a clean stop => the server stays
down until next logon/manual start. Suggested owner fix (installer template):
flush + re-raise / os._exit(1) after writing the traceback.

## R-2 (LOW-MEDIUM) crash.log truncation destroys prior evidence pre-health
run_waitress.py:3: crash.log opened 'w' at every start. The previous crash's
traceback is wiped before the new process proves healthy; a crash-loop keeps
only the latest (possibly empty) log. Suggest append/rotate.

## R-3 (MEDIUM-LOW) Non-atomic batch sync can wedge all future saves
- custom_save_state (app.py:1548-1585) persists main state atomically (good),
  then rewrites each touched batch with direct open('w') (no tmp/replace,
  no fsync, no retry, no error handling).
- load_batch (app.py:1474-1479) has NO corruption guard: torn JSON raises.
- Crash between open('w') and completed dump => torn batch file => every
  later custom_save_state raises at line 1557 (after main save, so state is
  persisted but the request 500s) until manual repair. Claim path (line 841)
  also raises instead of skipping the torn batch.
- Suggest: same atomic-write helper for batches + load_batch returning None
  (or quarantine) on JSONDecodeError.

## R-4 (LOW) load_state retries corruption as if transient
app.py:466: JSONDecodeError retried 20x with 50ms sleeps. Atomic replace
makes torn reads near-impossible; the retries only delay the raise by ~1s.
Harmless; optionally retry only PermissionError/IOError.

## Corroborated GOOD (no action)
- Main save_state: per-thread tmp + flush + fsync + os.replace + 20x
  PermissionError retry (DLQ-06 style). Atomic and Windows-aware.
- load_state: fails closed (sys.exit 1) on unknown future schema; setdefaults
  keep old states loadable; v1->v2 migration preserves identity.
- Tmp litter (STATE_FILE.<ident>.tmp) after a crash is ignored by load and
  overwritten per-thread; no corruption vector, cosmetic only.

## Net
Steady-state persistence is sound; the crash-loop corners (R-1/R-2/R-3) are
where a long acceptance run could silently stall. All three are small,
owner-scoped, testable-with-shell fixes — parked, not applied.
