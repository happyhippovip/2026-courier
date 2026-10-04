# MUSE-45 T-L1 — Finding survival on fix-cb1-new @ 329abd80 (read-only)

Branch switch (see INCIDENT packet) moved the tree. Each prior finding re-checked
against the NEW tree. Shell still DOWN; static only.

## SURVIVES (same file, same defect shape)

- R2 claim_task stray blanks: server/app.py:267/270/276 still carry trailing-space
  blank lines (older/smaller server file here: claim at :263, main at :561).
  Cosmetic, P3 read-only, note only — as before.

## MUTATED (same file, new shape — successor notes)

- F3 stop.bat: mechanism CHANGED from CIM command-line match to
  `taskkill /F /T /IM python.exe /FI "WINDOWTITLE eq CourierWindowsWorker*"`.
  Still not exact-PID-identity (title-filtered mass kill + child tree), but
  narrower than the old pattern. Old F3 text vacated; successor recorded here.
- Worker start chain: start.bat is now foreground `uv run python daemon.py`
  (no run_loop.bat loop, no log redirect, no start /B). run_loop.bat,
  stop_safe.py, worker_status.py, start.py do NOT exist on this branch.
  T-B worker-chain section superseded here.

## VACATED on this branch (cited files absent — findings stay branch-scoped
## to the pre-switch tree, preserved in their packets)

- H1 (soak_test.py), G2 (wall config pins), T-A wall verify: windows_muse_wall/
  absent. F4 orphan launchers: both files absent with the dir.
- G1 + DLQ-08/V2 + T11 pins: courier_continue.py absent.
- V1 + DLQ-01/02/06 + T-I pins: agent_handoff_ledger.py absent.
- F1/F2 dual-8080: single server path here (flask app.run 0.0.0.0:8080 at
  :561-562; no waitress/installer path). No dual binder possible.
- R1 artifacts dup: no "artifacts" in this branch's run_chief_commander.py.
- DLQ-05 quota machinery: no provider_locks/worker_quota_pools anywhere in
  server/app.py (older claim: capability match + cost routing only).
- T-C S1/S2/S3, T-E dedupe, T-H locus, T-D sweep: coordination + ledger +
  wall-test files absent (their evidence was old-tree).

## STANDS (untracked, switch-proof)

- runtime/**: slot states, 16 DONE jobs/logs, my MUSE-45 claim — intact.
- T-J WIN-01..05 observation (state-level; T-L3 re-confirms).
- All packets + slot corpus as pre-switch evidence (pins frozen, primacy kept).

## Verdict

Portable survivors: R2 + F3-successor + worker-chain delta (this packet).
Everything else is either vacated-branch-scoped or untracked-intact. No fix
attempted anywhere (foreign scopes + no runner + frozen RC discipline).
