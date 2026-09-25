# Windows Antigravity Recovery – 2026-09-25

Status: **NOT yet confirmed working.** The UI behind the certificate warning is still unproven.

## Current state (reported by Dennis, latest run on the machine)

- Antigravity **2.16.0** starts again with:

  ```powershell
  Start-Process "$env:LOCALAPPDATA\Programs\antigravity\Antigravity.exe" -ArgumentList '--disable-gpu','--disable-gpu-sandbox'
  ```

- Log line: `Starting app (v2.16.0)`, followed by a dynamic local UI URL.
- Last UI URL: `https://127.0.0.1:50367/`
- **The port is NOT fixed.** Earlier ports included 51131, 51156 and others. Always use the
  last `Local: https://127.0.0.1:<port>/` line from `main.log`.
- Browser on that URL shows `Ihre Verbindung ist nicht privat` / `NET::ERR_CERT_AUTHORITY_INVALID`.
  This is the local 127.0.0.1 self-signed certificate warning.

## Logs

- Main: `C:\Users\lol\AppData\Roaming\Antigravity\logs\main.log`
- Language server: `C:\Users\lol\AppData\Roaming\Antigravity\logs\language_server.log`

## Next step (not done yet)

In the browser: **Erweitert → Weiter zu 127.0.0.1**, then confirm that the Antigravity UI
actually loads. Only then report it as working.

## Update 2.17.0

The start log shows Antigravity downloading 2.17.0 in the background.
Until 2.16.0 is fully proven:

- do NOT restart Antigravity,
- do NOT apply the update,
- do NOT activate 2.17.0.

Note: nothing is technically blocking the update. The built-in auto-updater keeps
downloading it and installs it when the app quits ("Auto install update on quit" in `main.log`).

## Historical fix

- Desktop shortcut `Antigravity (Fix).lnk`
  - Target: `C:\Users\lol\AppData\Local\Programs\antigravity\Antigravity.exe`
  - Arguments: `--disable-gpu --disable-gpu-sandbox`
- `Antigravity NEUSTART.lnk` → `Antigravity-Neustart.ps1`. It reads the last URL from `main.log`.

## Earlier finding the same day (Claude session, before Dennis uninstalled and reinstalled Antigravity)

- Cause of the start crashes, proven by comparison: the user profile ACL (`C:\Users\lol`,
  inherited by `%LOCALAPPDATA%`) carries about 200 AppContainer entries plus the groups
  `CodexSandboxUsers` and `MuseSandboxUsers`. With that ACL the Chromium GPU sandbox fails:
  the GPU process crashes 9 times (0x80000003), then "GPU process isn't usable. Goodbye."
  The same app copied to a folder with a clean ACL started without any flags.
- `--disable-gpu-sandbox` alone was enough (2.17.0 was tested with it, including restart,
  a Windows reboot and a real Google reply via `agy -p`).
- That setup no longer exists: Antigravity was uninstalled, and the autostart entry was removed
  (backup `.reg` exists).

## Observed, not proven as cause

- `Failed to list WSL distros` in `main.log`. Do not repair it.

## Safety limits

- Do not delete credentials, profiles, `.gemini` or `.gemini_alt`.
- No ACL or sandbox repair.
- No broad `taskkill`; only exact PIDs.
- P3 is read-only: `server/app.py`, `server/run_waitress.py`, `server/launch_server_hidden.vbs`.
