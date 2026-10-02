# M5 — WORKER_HEARTBEAT_RESTART (Muse 5)

Stand: 2026-09-28, Quelle: Code-Reads + `central_state.json` (kein Live-Server)

## USER_PROBLEM (Operator-Sicht)
Der Worker ist weg / startet neu — was passiert mit seinem Task? Wartet Courier
ewig, startet blind neu, oder stellt er mir eine Frage?

## CURRENT_RUNTIME_TRUTH (belegt)
- Daemon heartbeated am Schleifenkopf (alle ~10 s, `daemon.py:305-313`); Server
  nennt Worker nach 300 s ohne Zeichen stale (`app.py:425-431`).
- Watchdog ruft alle 60 s `POST /tasks/reclaim_stale` (`courier_watchdog.py:27-39`).
- Reclaim: DISPATCHED-auf-stale-Worker → `HUMAN_REQUIRED` + Goal BLOCKED
  (`EFFECT_AMBIGUOUS`, `:436-452`); `reclaimed` ist hart 0 — NIE Blind-Replay.
- Restart-Pfad: `register(current_task=None)` → gleiche Quarantaene
  (`WORKER_RESTARTED_AND_LOST_STATE`, `:195-208`); Daemon-Crash in STARTED →
  Release ohne Re-Execute (`daemon.py:293-302`).
- Lease-Loch: 600-s-Task-Block vs 300-s-Reclaim — gesunder Lang-Task wird
  mid-run quarantiniert; danach 409 → REJECTED → RELEASE_PENDING → Release
  (idempotent, kein Wedge — Downgrade von HIGH auf MEDIUM bereits in Vorarbeit).
- Live-Fall: `task-replace-001` DISPATCHED an `NEW-WIN-PC-01`, `last_seen`
  ~11 Tage alt → wuerde beim naechsten Watchdog-Tick quarantinieren, FALLS ein
  Server liefe. Kein laufender Server beobachtet.

## VERDIKT
M5-CLOSED (Code-Seite): Restart-Semantik = sicher-durch-Quarantaene. Preis:
Fehlalarm-Quarantaene gesunder Lang-Tasks + jeder Crash endet beim Menschen
(`resume retry` noetig). Kein automatischer Wiederanlauf — das ist Design, kein Bug.

## ACCEPTANCE_REQUIREMENT
M5.1: Haengende Dispatches zeigen `STALE_SUSPECT` + Quarantaene-Grund statt ewig
  `DISPATCHED` (vgl. UA-C01.4).
M5.2: Nach Quarantaene sieht der Operator genau EINEN empfohlenen Schritt
  (`resume retry` nach Effekt-Pruefung), nicht drei Routen zum Raten.

## MISSING_SYSTEM_SUPPORT
- Kein Stale-Indikator in `/status`; kein Quarantaene-Grund im UX-Vokabular.

## PREPARABLE_NOW
- Dieses Paket + Quarantaene-Grund-Liste (2 Gruende, s. o.).

## BLOCKED_UNTIL
- Lebend-Beobachtung (RUN) fuer Timing-Feinschliff — Semantik steht ohne sie.

## NEXT
M6 (Prozess-Reap/Timeout) — M5 liefert: Transport-Seite nach Timeout ist sauber.
