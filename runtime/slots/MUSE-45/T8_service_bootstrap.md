# T8 RESULT — Service/Bootstrap wiring (install_*.ps1 vs real entry points)

MODE: static read-only (shell down, no execution). All claims OBSERVED-in-file unless marked.

## Wiring map (OBSERVED)

| installer | mechanism | target | entry point | status |
|---|---|---|---|---|
| scripts/install_motor_service.ps1 | ScheduledTask CourierMotor, AtLogon | scripts/start_motor.bat | server.app + courier_github_dispatcher + courier_watchdog (3x start /B, .venv_service python) | EXISTS, all 3 modules have run_loop mains |
| scripts/install_verifier_service.ps1 | ScheduledTask CourierVerifier, AtLogon | scripts/start_verifier.bat | scripts.courier_verifier (foreground in task) | EXISTS |
| server/install_server_service.ps1 | HKCU Run CourierServer + immediate WMI start | launch_server_hidden.vbs -> run_waitress.py | waitress serve(server.app, 0.0.0.0:8080) | EXISTS, generated files present |
| scripts/windows_worker/install_service.ps1 | ScheduledTask CourierWindowsWorker, AtLogon | start.bat -> run_loop.bat | daemon.py infinite restart loop | EXISTS |
| scripts/windows_worker/bootstrap.ps1 | interactive setup + install + health wait | install_service.ps1, logs/worker.log | waits "Registered successfully"/"HTTP Daemon started", fails on "FATAL" | ALL 3 STRINGS PRESENT in daemon.py |
| server/start_server.bat | manual dev start | uv run -m server.app | flask dev server | EXISTS |
| launch_all.bat | manual dev all | motor + verifier + worker bats | sets local keys in env | EXISTS, no server-service path |
| scripts/bootstrap_ai_ops.sh | doc scaffolding, idempotent, never overwrites | ops/ai/*.md | n/a (not a service) | OK, out of scope |

## Findings

F-T8-1 (MEDIUM) DOUBLE SERVER BIND RISK.
server/app.py:1589-1590 runs flask on 127.0.0.1:8080 (motor path);
run_waitress.py serves same app on 0.0.0.0:8080 (server-service path).
Both installers coexisting => second binder fails on :8080. No port guard,
no mutual-exclusion note. launch_all.bat avoids it (motor only), but the two
installers do not warn about each other.

F-T8-2 (MEDIUM) "START ON BOOT" CLAIM IS INACCURATE.
Motor/verifier/worker tasks use -AtLogon + Interactive principal; server uses
HKCU Run. All require an interactive logon and die at logoff. Terminal-exit
survival: YES (task/HKCU/WMI escape the console job). Logoff survival: NO.
RC proof steps 2-3 ("OS-owned, independent of interactive terminal/agent")
hold only while the Windows session stays logged on. True boot persistence
would need AtStartup/SYSTEM (writer-scope decision, NOT made here).

F-T8-3 (LOW) UNDOCUMENTED ORDERING DEPENDENCY.
Only server/install_server_service.ps1 creates .venv_service (uv venv).
install_motor_service.ps1 consumes .venv_service but never creates it =>
standalone motor install fails. Same for verifier (uses .venv_service).

F-T8-4 (LOW) INCONSISTENT LOG HOMES.
Motor -> repo-root logs\; verifier -> scripts\verifier.log (inside source
tree); worker -> scripts\windows_worker\logs\; server -> server\crash.log +
server.log. Verifier log pollutes the source tree.

F-T8-5 (OK) BOOTSTRAP HANDSHAKE SOUND.
bootstrap.ps1 health strings all emitted by daemon.py (lines 27/60/340);
UAC fallback (hidden start.bat) is session-scoped and documented inline;
config.json stores non-secrets only, API key via OS keyring. No defect.

F-T8-6 (LOW) INSTALLER REWRITES TRACKED-LOOKING P3 FILES.
install_server_service.ps1 regenerates server/run_waitress.py and
server/launch_server_hidden.vbs via Set-Content on every run. If these are
git-tracked, installed copies can drift from repo copies outside git flow
(can't verify tracked-state: no shell). Owner: server installer, not P3 code.

## Disposition
Read-only mission: NO FIXES APPLIED. Findings handed to writer owners
(motor/server installer scope). No files outside runtime/slots/MUSE-45 touched.
