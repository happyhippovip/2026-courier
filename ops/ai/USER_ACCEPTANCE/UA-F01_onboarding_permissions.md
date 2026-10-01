# UA-F01 — Onboarding / Permissions: Welche Daten und Rechte nutzt Courier?

Prioritaet: F (Onboarding / Permissions)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger)

## USER_PROBLEM
Bevor ich Courier installiere, will ich wissen: Welche Keys, welche
Netz-Adressen, welche Systemrechte, welche meiner Daten — und wie werde ich das
alles wieder los? Heute muss man das aus 5 Dateien puzzeln.

## CURRENT_RUNTIME_TRUTH (belegt)
- Zwei Keys, muessen verschieden sein: `COURIER_API_KEY` (Worker/Server) und
  `COURIER_VERIFIER_API_KEY` (Verifier); sonst 503 bzw. Start-Abbruch
  (`server/app.py:12-44`, `deploy/run-supervisor.sh:3-5`).
- `scripts/windows_worker/bootstrap.ps1:60-66` schreibt den Worker-Key als
  KLARTEXT in `config.json` (gelesen: Datei enthaelt heute Server+ID, kein Key).
- `scripts/windows_worker/install_service.ps1:1-15`: Scheduled Task
  `CourierWindowsWorker`, Trigger AtStartup, Principal SYSTEM + Highest.
  Erfordert Admin; Deinstallation = Unregister (kein Uninstaller gefunden).
- Daemon fuehrt Task-`instruction` als natives PowerShell aus (`-EncodedCommand`,
  `daemon.py:210-217`); Default-Server ist eine LAN-IP
  (`http://192.168.178.162:8080`, `daemon.py:10`), Verifier/Watchdog defaulten
  auf `127.0.0.1:8080`.
- Server bindet `0.0.0.0:8080` (`app.py:567`); State unter
  `server/state/central_state.json` (atomic tmp+replace); Artifact-Bytes landen
  im Server-Store (`server/state/artifacts`, 16 MiB-Cap); Lockfile in `%TEMP%`.
- Spend-Limit 0,00 EUR, fail-closed (README); keine Zahlungsdaten im Repo.

## ACCEPTANCE_REQUIREMENT
UA-F01.1: EIN Permission-Manifest vor der Installation: pro Eintrag
`WAS | WOZU | WO_GESPEICHERT | WIE_WIDERRUFEN`. Mindestens: 2 Keys, Server-URL,
  SYSTEM-Task, PowerShell-Ausfuehrung, State-/Artifact-Pfade, Lockfile, Port.
UA-F01.2: SYSTEM/Highest und AtStartup sind OPT-IN mit Begruendung; dokumentierte
Least-Privilege-Variante (User-Task, kein Boot-Start) existiert.
UA-F01.3: Key-Regeln: nie ins Repo, nie in Screenshots/Logs; Klartext-`config.json`
wird als Risiko benannt + Alternative (nur Env/Keychain) gezeigt.
UA-F01.4: Deinstallations-Pfad ist dokumentiert (Task-Unregister + Key-Rotation
  + State-/Artifact-Loeschung).

## MISSING_SYSTEM_SUPPORT
- Kein Manifest, keine Least-Privilege-Anleitung, kein Uninstaller.
- Kein Keychain-Pfad auf Windows (nur Env oder Klartext-Config).
- Keine Install-Zustimmung, die Manifest-Punkte einzeln bestaetigt.

## PREPARABLE_NOW
- Dieses Dokument + Manifest-Entwurf (Tabelle, aus Runtime-Truth oben).
- Onboarding-Checkliste (5 Minuten, ohne Shell-Know-how lesbar).

## BLOCKED_UNTIL
- Owner-Entscheid: SYSTEM vs User-Account als Default.
- Keychain-/Secret-Store-Entscheid Windows.

## NEXT
UA-G01 (Update/Rollback/Last-Known-Good).
