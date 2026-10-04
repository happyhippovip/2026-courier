# M5 — WORKER_HEARTBEAT_RESTART (Muse 5)

Stand: 2026-09-28. Statisch (Code gelesen, keine Prozesse beobachtet).

## Befund: Lease-Loch bei langen Tasks (belegt)
- Server: `reclaim_stale` quarantaeniert DISPATCHED-Tasks staler Worker
  (Schwelle 300 s, `server/app.py:425-458`) → HUMAN_REQUIRED + Goal BLOCKED.
  Kommentar `:434-435` sagt: ohne Beweis "nie gestartet" kein Replay — korrekt.
- Windows-Daemon: Heartbeat NUR am Schleifenkopf (`daemon.py:330-338`), danach
  blockiert `communicate(timeout=600)` (`:239`). Jeder gesunde Task >300 s wird
  mitten im Lauf quarantaeniert; sein spaetes Result → 409/400 → REJECTED →
  RELEASE_PENDING → Freigabe. Effekt ohne Result, Task in HUMAN_REQUIRED.
- Mac-`run_agy`: gleiches Muster, 300 s-Timeout (`daemon.py:305`) exakt an der
  Schwelle — Grenzfall, Rennfenster offen.
- Mac-`run_muse`: IMMUN — In-Task-Heartbeat alle 30 s (`daemon.py:373-376`).
  Referenzmuster.
- Register-Release funktioniert statisch: `current_task=None` bei Server-Dispatch
  → HUMAN_REQUIRED/Quarantaene statt Replay (`app.py:195-202`).

## Urteil
- Kein Crash-, sondern ein ZEIT-Problem: gesunde Worker verlieren lange Tasks
  an die Quarantaene. Kein Datenverlust (Quarantaene statt Replay), aber
  HUMAN_REQUIRED ohne echten Grund + verlorene Rechenzeit.
- Lebend-Beispiel im State: `task-replace-001` DISPATCHED an toten Worker
  (`central_state.json`) — faellt beim naechsten `reclaim_stale` in Quarantaene
  (erwartet, per Design).

## ACCEPTANCE / REQUIREMENT (Spec, kein Code-Umbau in diesem Fenster)
- M5.1: In-Task-Heartbeat (Muse-Muster) wird der KANONISCHE Weg fuer Tasks,
  die laenger als die halbe Schwelle laufen koennen (Ziel: <150 s ohne Beat).
- M5.2: Alternativmenue (Owner entscheidet): (a) In-Task-Beat überall,
  (b) Server-Grace ab Claim (braucht Claim-Zeit-Tracking — fehlt heute),
  (c) Timeouts ≤300 s alignieren (600-vs-300-Widerspruch heute).
- M5.3: Nutzer-Regel (fuer UA-C01): "Tasks >5 Min auf Windows/Mac-Agy landen
  derzeit in HUMAN_REQUIRED — kein Fehler von dir, Resume→Retry ist der Weg."

## MISSING_SYSTEM_SUPPORT
- Kein In-Task-Beat im Windows-Daemon und im Mac-Agy-Pfad.
- Keine Claim-Zeit im State (fuer Grace-Option).
- Keine sichtbare "STALE_SUSPECT"-Warnung vor der Quarantaene.

## BLOCKED_UNTIL
- Owner-Entscheid M5.2 (a/b/c). Umbau + Beweis folgen spaeter, nicht hier.

## NEXT
M6 (Process-Reaping — was nach Timeout mit dem Kindprozess passiert).
