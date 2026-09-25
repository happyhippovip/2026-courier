# WINDOWS RUNTIME MAP
BOUND_TO_CODE_HEAD: 7c495f8c1b31293f8d3a5465035d2d3f61cbd3a7
UPDATED_AT: 2026-09-18T09:23:33+02:00
LAST_OBSERVED_WINDOWS_RUNTIME_SHA: 2b9e34fb8b88bde54507e4c21e1241744a746dbf
WINDOWS_RUNTIME_SHA_CURRENT: UNKNOWN
WINDOWS_HEALTH_CURRENT: UNKNOWN
WINDOWS_STATUS_CURRENT: UNKNOWN
WINDOWS_DIRTY_STATE: UNKNOWN (Mac lane does not touch Windows; observed only)
SOURCE: scripts/studio_local_tools.py observer hosts.windows
NOTE: The prior observation predates the current code base and is historical only. Re-observe before physical acceptance.

## Antigravity observation 2026-09-25 (user-reported machine evidence, not re-verified by cloud)
- Version 2.16.0 running; 2.17.0 downloaded in background (not applied).
- Processes: several `Antigravity.exe`, `language_server.exe`.
- 127.0.0.1 listeners: 51026, 51027 (language_server.exe); 50363, 50366 (Antigravity.exe).
- HTTPS probe: 51026 = 200; 51027, 50363, 50366 = 000 -> CURRENT_LIVE_HTTPS_PORT=51026 (dynamic, will change).
- Logs: `%APPDATA%\Antigravity\logs\main.log`, `...\language_server.log`.
- Open: UI_VISIBLE, LANGUAGE_SERVER_CONNECTED, AGENT_FEATURES_WORKING, GOOGLE_E2E (not yet proven).
- Rules: docs/WINDOWS_RUNTIME_RULES.md section 11.
