# WIN Acceptance EVIDENCE — full live pass 2026-10-07 (real Windows 10, Python 3.12.10)

HEAD: `integration/v1` = `b9fc486ac` in detached worktree (removed after run).
Isolation: `COURIER_HOME=%TEMP%\courier_accept_1`, ports 8765/8766, `PYTHONPATH=<worktree>`.
Build: `build_launcher.ps1` OK → `Courier.exe` 12800 bytes.
Scope respected: no touch of #133/#135 files; machine-wide install/uninstall
NOT run on dev box (VM-only runbook stays in GAP 3 checkpoint).

## Phase 1 — first launch → worker → job (PASS)

- `LAUNCHER_PID=4860`, token issued (len 43).
- `HEALTH={"mode":"normal","head_seq":1,...,"python":"3.12.10"}`.
- `HUB_STATUS={"controller":"running",...}`.
- Synthetic task `task-66ce…` → `COMPLETE`; Hub `/hub/api/home` lists it
  under done (count 1).
- Owned tree: launcher + 3 python (serve/host/hub) + 3 conhost.

## Phase 2 — close → no orphan (PASS, plus 1 finding)

- `POST /v1/shutdown` → `{"status":"STOPPING"}` (graceful path exists).
- `Stop-Process` on owned launcher PID only (no name-based kill):
  `SURVIVORS=` (empty), `STRAYS=` (empty), launcher gone, port closed.
- Rule 0 step 7 holds for the PID-exact path. The shipped `stop.bat`
  (system-wide `taskkill /IM`, GAP 1) was deliberately NOT used.

## Phase 3 — restart → reconnect/live agent (PASS)

- Relaunch same home: `LAUNCHER2_PID=22872`, health normal,
  `head_seq=10` (journal continued, not reset), hub running.
- Gen-1 task still under done (count 1) → state reconstruction proven.
- NEW task `task-d8b0…` → `COMPLETE`, claimant pid 2944 ∈ gen-2 tree
  `(22872,11168,2944,9352,12028,23424,19376)` → post-restart worker
  generation executed it. `GEN1_STILL_ALIVE=` (empty).

## Phase 4 — user-data snapshot + cleanup (PASS)

- Home contained: `courier.db` (45056 B) + `-wal` (263712 B) + `-shm`,
  `logs/`, `artifacts/`, `outbox/`, `run/`, `config.json` — i.e. exactly
  the data the uninstall contract (GAP 3 / #157 parse-check) must keep
  (`courier.db`, `logs`) vs remove (`config.json`, `run/`).
- Live `uninstall.ps1` run still UNPROVEN (needs scratch VM).
- Final: `FINAL_SURVIVORS=` `FINAL_STRAYS=`; worktree removed; TEMP
  home + state file removed. No residue left running.

## Verdict

Green live pass on real Windows for: first launch, worker start, job
execution, close-by-PID with zero orphans, restart with state
reconstruction, post-restart live-agent execution, user-data presence.
Open (not on dev box): machine-wide install.ps1/uninstall.ps1 live run;
shipped stop.bat still contradicts the quality bar (GAP 1 for L6).
