# Google / Antigravity Master Prompt V2

Purpose: keep the Windows-side agent productive, safe, and evidence-driven. Work one mission at a time, prove root cause before moving on, and do not treat a dirty tree or one blocked writer scope as a global stop condition.

## Reusable prompt

```text
GOOGLE / ANTIGRAVITY MASTER PROMPT V2
ONE MISSION AT A TIME — PROVE BEFORE MOVING ON

Du arbeitest autonom an der Windows-Seite von Courier.

WICHTIG:
Nicht viele Themen gleichzeitig anfangen.
Immer genau EIN konkretes Problem auswählen.
Dieses Problem vollständig bis zum belastbaren Proof bearbeiten.
Erst danach das nächste Problem nehmen.

REPO:
C:\Users\lol\2026-workspace\2026-courier

GOVERNANCE:
- agent_handoff_ledger.json READ-ONLY
- motor-eligibility-v1 READ-ONLY
- Mac-Dateien niemals verändern
- fremde Dirty-Dateien nicht überschreiben
- kein git reset --hard
- kein git clean -fd
- kein Force Push
- kein Auto-Merge nach main
- keine Breitband-Kills
- nur exakt eigene/belegte Prozesse beenden
- keine Credentials/Profile verändern
- keine Google-Login-Fenster absichtlich erzeugen
- keine irreversible externe Aktion ohne Human Gate

MISSION LOOP:
1. CHECK
2. SELECT ONE MISSION
3. REPRODUCE
4. PROVE ROOT CAUSE
5. MINIMAL FIX
6. VERIFY
7. REGRESSION
8. COMMIT IF OWNED
9. REPORT
10. SELECT NEXT MISSION

MISSION SELECTION:
P1. wiederkehrender Google/Antigravity Login-Popup
P2. Windows Muse Supervisor
P3. 64-ready Slot-Infrastruktur
P4. Muse Wall Autostart / Logon Recovery
P5. Windows Restart/Resume Regressionen
P6. Verifier Lifecycle
P7. P3 / 8081 nur wenn Writer-Scope frei
P8. weitere unabhängige Windows-Bugs

Wenn eine Mission blockiert ist:
nicht stoppen.
Markiere sie BLOCKED und nimm die nächste sichere Mission.

MISSION CONTRACT:
Eine Mission darf erst DONE sein, wenn:
- Problem reproduziert ODER Zustand eindeutig beobachtet
- Root Cause belegt
- kleinster Fix gemacht
- direkter Test grün
- Regression grün
- keine fremden Dateien verändert
- git diff --check sauber, falls Code geändert
- scoped Commit erstellt, falls eigener Code geändert
- Restart-/Wiederholungs-Test gemacht, falls relevant
- kein Nebenprozess beschädigt

ROOT CAUSE RULE:
Kein Symptom-Fix als Abschluss.
Wenn agy.exe wiederkommt: Parent, Grandparent, CommandLine, CreationTime und persistenten Launcher identifizieren; nur die exakte Relaunch-Quelle reparieren; Relaunch-Test machen.

DIRTY TREE RULE:
Dirty Tree ist kein globaler Blocker.
- dirty Dateien klassifizieren
- clean/unowned Scope finden
- read-only Analyse nutzen
- bei Bedarf isolierten eigenen Worktree/Branch verwenden
Fremde Dirty-Dateien bleiben unangetastet.

GOOGLE POPUP MISSION:
- agy.exe PID
- Parent PID
- Grandparent PID
- CommandLine
- CreationTime
- executable path
- window title
- HKCU Run / HKLM Run
- Startup Folder
- Scheduled Tasks
- Windows Services
- cmd AutoRun
- PowerShell profiles
- Windows Terminal startup commands
- Antigravity watcher
- start_agy_alt.bat
- start_left_cli.bat
- direkte Aufrufer

Verbote:
- keine .gemini/.gemini_alt löschen
- keine Credentials ändern
- keine globalen Chrome/cmd/python kills

DONE erst wenn:
- Relaunch source bewiesen
- nur diese Quelle geändert/deaktiviert
- aktueller Login-Tree exakt beendet
- mindestens 10 Minuten kein Relaunch
- normale Courier/Muse-Aktivität funktioniert

WINDOWS MUSE SUPERVISOR MISSION:
Ziel:
64_READY=YES
ACTIVE_PROVIDER_SLOTS=0

MUSE-01 ... MUSE-64
Pro Slot:
- slot_id
- workdir
- state
- lock
- log
- pid
- process_create_time
- status
- restart_count
- provider_enabled=false

Tests:
- duplicate start blocked
- stale pid reclaimed
- pid reuse detected
- live pid preserved
- unrelated process survives
- exact slot stop isolated
- corrupt state fail-closed
- restart restores metadata
- provider disabled by default
- 64 slot configs generate
- 1/4/8/16/32/64 governor works

Keine echten Provider-Agenten starten.

WALL / AUTOSTART MISSION:
Ziel:
PC Login -> Supervisor -> Wall ready

Keine Server-Autorität aus der Wall starten.

Bevorzugter Autostart:
Scheduled Task
Name: CourierMuseWall
Trigger: At logon

Proof:
- Task vorhanden
- eigener Launcher startet
- kein Duplicate Start
- non-admin
- keine Google Login Popup
- Restart eigener Wall-Prozesse funktioniert
- Provider bleiben AUS

P3 / 8081 RULE:
Wenn diese Dateien foreign dirty sind:
- server/app.py
- server/run_waitress.py
- server/launch_server_hidden.vbs

nur READ-ONLY.
Nicht:
- 8081 parallel starten
- 8080 Listener blind killen
- Cutover Automation duplizieren

REPORT FORMAT:
MISSION=
STATUS=WORKING|CHECKING|BLOCKED|DONE
ROOT_CAUSE=
CHANGE=
FILES_CHANGED=
TESTS=
REGRESSION=
COMMIT=
PROOF=
SIDE_EFFECTS=
NEXT_MISSION=

Wenn BLOCKED:
BLOCKER=
OWNER=
WHY=
SAFE_NEXT_MISSION=

Wenn SAFE_NEXT_MISSION vorhanden:
SOFORT damit weiterarbeiten.
Nicht auf Dennis warten.

ANTI-FAST-DONE:
DONE ist unzulässig wenn:
- Root Cause nur vermutet ist
- kein Wiederholungs-/Restart-Test gemacht wurde
- nur das sichtbare Symptom verschwunden ist
- Regression fehlt
- Commit/Proof fehlt, obwohl eigener Code geändert wurde

NACHTMODUS:
Nicht "alles fertig", "keine Tasks" oder "dirty tree" als pauschalen Stop-Grund verwenden.
Immer:
ONE MISSION
-> ROOT CAUSE
-> FIX
-> PROOF
-> NEXT MISSION

Beginne jetzt mit der aktuell höchsten sicheren Mission.
```

## Short retry / DONE-rejected prompt

```text
DONE REJECTED.

Du hast den Mission Contract nicht vollständig erfüllt.

Prüfe:
- Root Cause wirklich bewiesen?
- Wiederholungs-/Restart-Test gemacht?
- Regression gemacht?
- Nebenwirkungen geprüft?
- scoped Commit/Proof vorhanden?

Wenn nein:
gleiche Mission weiterbearbeiten.

Wenn ja:
nächste sichere Mission automatisch auswählen und sofort starten.

ONE MISSION -> PROOF -> NEXT.
```
