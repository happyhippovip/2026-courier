# Google Antigravity öffnen (Windows one-click starter)

`Open-GoogleAntigravity.ps1` opens the Antigravity UI port that is live right now.

```powershell
# once: create the Desktop shortcut "Google Antigravity öffnen"
powershell -NoProfile -ExecutionPolicy Bypass -File .\Open-GoogleAntigravity.ps1 -InstallShortcut
# run (or double-click the shortcut)
powershell -NoProfile -ExecutionPolicy Bypass -File .\Open-GoogleAntigravity.ps1
```

Output lines: `ANTIGRAVITY_RUNNING=` or `STARTING_ANTIGRAVITY=`, then `LIVE_UI_PORT=<port>`,
or `ANTIGRAVITY_UI_NOT_FOUND` (exit 2) with the candidate ports it tried.
`-NoStart` only looks and never starts Antigravity.

## Hard rules (observed on the Windows PC, 2026-09-25)

- **Do not enable "Allow/Enable Confirmations"; do not change confirmation settings.**
  If prompted, leave disabled / cancel / no. Enabling it dropped the working agent connection.
- UI ports are dynamic (seen: 51131, 51156, 50367, 50458, 51026). Never hard-code one.
  A port from `%APPDATA%\Antigravity\logs\main.log` counts only if it listens and answers HTTPS 200 now.
- Proven start: `Antigravity.exe --disable-gpu --disable-gpu-sandbox`
  (`%LOCALAPPDATA%\Programs\antigravity\`). The script starts it only when no `Antigravity.exe` runs.
- Version 2.16.0 works; 2.17.0 was downloaded in the background. Do not apply it blindly and do
  not delete updater files.
- No reinstall, no profile or account changes, no hosts-file edits, no broad taskkill.
- Success for Google E2E means a real Antigravity agent reply to
  `Antworte exakt: GOOGLE_E2E_OK_20260925`, not a local echo.

Not verified on Windows from the cloud: the script was written and reviewed statically only.
