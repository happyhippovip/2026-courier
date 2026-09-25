# Windows Antigravity Recovery – 2026-09-25

Status: **WORKING (E2E PASS)**

## Confirmed Working State
- **Antigravity Version**: 2.16.0
- **Install Path**: `C:\Users\lol\AppData\Local\Programs\antigravity\Antigravity.exe`
- **Start Flags**: `--disable-gpu --disable-gpu-sandbox`
- **Dynamic Port Rule**: The port is not fixed. The currently listening port must be read dynamically from `main.log` (e.g., `Local: https://127.0.0.1:<port>/`) and verified via `Get-NetTCPConnection`.
- **Zertifikatswarnung**: The `NET::ERR_CERT_AUTHORITY_INVALID` warning for 127.0.0.1 is normal. Bypassing it locally (Erweitert -> Weiter) or via script is expected.
- **E2E Beweis**: PASS (Google Agent responded successfully with `ANTIGRAVITY_E2E_OK_20260925`).

## Logs
- **Main Log**: `C:\Users\lol\AppData\Roaming\Antigravity\logs\main.log`
- **Language Server Log**: `C:\Users\lol\AppData\Roaming\Antigravity\logs\language_server.log`

## Update 2.17.0 Risk
- **UPDATE_PENDING=YES**
- The built-in auto-updater has downloaded version 2.17.0 (`Update has already been downloaded to C:\Users\lol\AppData\Local\antigravity-updater\pending\Antigravity-x64.exe`).
- A restart of Antigravity will likely apply the update automatically (`Auto install update on quit`).
- Because of this risk, **no unnecessary restarts should be performed**. The restart test is DEFERRED (`RESTART_TEST=DEFERRED_UPDATE_RISK`).

## One-Click Starter (Stable)
A reliable, one-click starter has been verified and resides on the Desktop:
- **Starter Path**: `C:\Users\lol\Desktop\Google Antigravity Stable.cmd` (wraps the `.ps1` script).
- It checks for existing healthy processes, prevents double starts, launches Antigravity with the correct flags if needed, waits for the dynamic port to become listening, and opens Chrome directly to the UI.

## Recovery Ablauf
If Antigravity stops working:
1. Do not manually kill processes globally.
2. Run `C:\Users\lol\Desktop\Google Antigravity Stable.cmd`. It will safely kill orphaned Antigravity processes, restart the app with the necessary GPU flags, and open the new dynamic UI URL.

## Known Non-Causes / Unproven Errors
- `Failed to list WSL distros`: This error in `main.log` is a known symptom/red herring. Do **not** attempt to repair WSL.

## Protected Items (DO NOT DELETE)
- Credentials and profiles
- `C:\Users\lol\.gemini`
- `C:\Users\lol\.gemini_alt`
- Do not run any ACL or sandbox repairs.
