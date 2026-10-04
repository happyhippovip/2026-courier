# M6 — PROCESS_REAP_TIMEOUT (Muse 6)

Stand: 2026-09-28. Statisch, Voll-Read der Timeout-Pfade.

## Befund: Timeout ohne Reap (belegt, HIGH-Charakter)
- Windows `run_task` (`scripts/windows_worker/daemon.py:236-247`):
  `communicate(timeout=600)`, bei Timeout (oder jedem Fehler) `except Exception →
  FAILED`, stderr=Fehlertext. KEIN kill/terminate/wait/taskkill in der Datei
  (Vollsuche, keine Treffer). Der Kindprozess laeuft VERWAIST weiter; der Daemon
  meldet FAILED und gibt den Task frei → Server-Retry = zweiter Effekt parallel
  zum noch laufenden ersten.
- Mac `run_agy` (`scripts/mac_worker/daemon.py:303-327`): identisches Muster
  (`communicate(timeout=300)`, `except → FAILED`, kein Kill).
- Mac `run_muse` (`:329-390`): SAUBER — Deadline-Überwachung, In-Task-Heartbeat,
  `finally` mit `cleanup_group(proc, identity)` + `ORPHANS_REMAIN`-Hartefall
  (`:383-389`, blockiert neue Execution bei Restwaisen). Referenzmuster.
- Timeout-Reste: Bei `TimeoutExpired` verwerfen beide `communicate`-Pfade
  partielle stdout/stderr (nur Exception-Text bleibt) — Beweisverlust, LOW.

## Urteil
- Zwei von drei Exec-Pfaden lassen Timeout-Kinder verwaist laufen. Das verletzt
  "genau einmal wirken" ueber den Retry-Pfad (M4-Kette schuetzt vor Doppel-
  RESULT, nicht vor Doppel-EFFEKT nebenläufiger Prozesse).
- `run_muse` zeigt, dass das Hausmuster existiert (Gruppen-Cleanup + Identitaet).

## ACCEPTANCE / REQUIREMENT (Spec, kein Umbau hier)
- M6.1: Jeder Exec-Pfad garantiert: nach Timeout ist der Kindprozess + Gruppe
  tot ODER der Task-Zustand heisst explizit `AMBIGUOUS` (nie still SUCCESS/FAILED
  bei lebendem Kind).
- M6.2: Kill folgt dem Identitaets-Prinzip (PID + Erzeugungszeit/Handle, kein
  blinder Name-Kill) — Muse-`identity`/`cleanup_group` als Vorlage.
- M6.3: Nutzer-Regel (fuer UA-C01): "Nach Timeout kann ein verwaister Prozess
  kurz weiterlaufen — Retry erst nach Reap-Bestaetigung" (bis Fix da ist).

## MISSING_SYSTEM_SUPPORT
- Kein Reap in `run_task` (win) und `run_agy` (mac).
- Kein `AMBIGUOUS`-Zustand im Task-Vokabular.
- Kein partielles Output-Backup bei Timeout.

## BLOCKED_UNTIL
- Owner-Umbau M6.1/M6.2 + Reap-Beweis (Kind tot inkl. Enkel; Unbeteiligte leben;
  PID-Wiederverwendungs-Koeder ueberlebt).

## NEXT
M7 (RUN1-Beweiskette — ob der RUN die echten Pfade ueberhaupt faehrt).
