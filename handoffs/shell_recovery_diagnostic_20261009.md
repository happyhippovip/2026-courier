# Shell-Recovery-Diagnose (Eigner: Dennis / Umgebung)

Stand: 2026-10-09, Sitzung 01a120cf. Alle Angaben belegt, nichts geraten.

## Fehlerbild

Jeder Shell-Aufruf scheitert VOR Ausführung beim Sandbox-Aufbau:

windows_elevated unified exec session launcher unavailable:
sandbox enforcement unavailable: Windows sandbox setup unavailable:
admit deny-read state C:\Users\lol\.local\share\muse\windows-sandbox/deny_read_acl_state.json:
host metadata ancestor permits unproved ACL/owner mutation

## Seit wann

- Diese Sitzung: von Beginn an (mehrfach identisch belegt).
- Vorgeschichte: gleicher Fehler seit 2026-09-25 über Sitzungen hinweg.

## Folgen

Keine Befehlsausführung, keine Tests, kein git-CLI, keine Prozess- oder
RAM-Prüfung, keine Live-Verifikation. Alle 52 Nightshift-Pakete daher
statisch (Code gelesen, nichts gelaufen). Bauen ohne Prüfen wäre blind.

## Nicht versucht (verboten)

Kein Sandbox-Bypass, kein --yolo, keine ACL-Massenänderung,
keine Freigabe-Umgehung. Flags stehen beim Start fest.

## Was du tun kannst

1. Muse ganz beenden und neu starten (frischer Sandbox-Aufbau).
2. Falls es wieder kommt: Ordner C:\Users\lol\.local\share\muse\windows-sandbox
   prüfen (Eigentümer/Rechte, Datei deny_read_acl_state.json lesbar?).
3. Falls nötig: Muse-Reparatur/Update.
4. Danach in neuer Sitzung ein Minimal-Test: Write-Output SHELL_ALIVE.
   Erst bei Erfolg: Golden-Suite fahren (höchster Wert).

## Danach entriegelt

Live-Nachweise für: Outbox-Verkeilung, Receipt-Verdrahtung,
Bearer-Dispatch, TOCTOU-Timing, VERIFYING-Cancel, Installer-Lauf.
