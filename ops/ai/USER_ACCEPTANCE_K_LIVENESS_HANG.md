# User Acceptance K — Liveness / Hängt-Erkennung (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: C-nah (Failure-Erkennung aus Nutzersicht: "hängt es oder arbeitet es?").

## USER_PROBLEM

Als Nutzer starre ich auf einen laufenden Task und weiß nicht: arbeitet
Courier noch — oder ist der Worker vor Minuten lautlos gestorben und ich
warte umsonst? Zwischen "alles gut" und "tot, aber niemand sagt es" gibt
es heute keine sichtbare Stufe.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Worker-Liveness existiert als Mechanismus: `last_seen` via
  `/workers/register`, `/workers/heartbeat`, Claim-Pfad
  (`server/app.py:209,243,265`); stale-Schwelle 300 s
  (`reclaim_stale`, `server/app.py:419`; Watchdog-Kommentar
  `scripts/courier_watchdog.py:11-12`).
- `POST /tasks/reclaim_stale` quarantäniert DISPATCHED-Steps staler Worker
  nachvollziehbar: `HUMAN_REQUIRED` + `recovery_reason =
  STALE_WORKER_EFFECT_AMBIGUOUS` + Goal → BLOCKED
  (`server/app.py:427-446`). Kein stilles Replay. Gut.
- ABER — Befund K-a (unbounded silent gap): `reclaim_stale` wirkt nur,
  wenn jemand es aufruft. Einziger Aufrufer im Repo ist
  `scripts/courier_watchdog.py` (60-s-Pollschleife, `:27-39`). Läuft der
  Watchdog nicht, bleibt ein toter Worker EWEIG als DISPATCHED stehen —
  der Nutzer sieht "ARBEITET", obwohl nichts mehr arbeitet.
- Befund K-b (6-Minuten-Funkstille auch im Bestfall): Mit Watchdog dauert
  die Erkennung bis zu 300 s stale-Schwelle + 60 s Poll-Latenz. In dieser
  Zeit gibt es kein nutzerlesbares "Antwort überfällig"-Signal.
- Befund K-c (Rohdaten statt Urteil): `/workers` liefert `last_seen` als
  rohen Epoch (`server/app.py:164-169`); `/status` nur Zähler
  (`:83-92`); `/health` nur `healthy` + Zeit (`:79-81`). Niemand sagt
  "Worker X antwortet seit N Sekunden nicht mehr".
- Befund K-d (toter Zweig): `reclaim_stale` antwortet immer mit
  `reclaimed_tasks: 0` (hardcodiert, `:451`); der Watchdog-Zweig
  `if reclaimed > 0` (`courier_watchdog.py:32-33`) ist damit toter Code.
  Quarantäne-Zählung (`quarantined_tasks`) funktioniert.
- Befund K-e: Die Server-eigene Liveness (`/health`) sagt nichts darüber,
  ob stale-Erkennung (Watchdog) läuft. "Server healthy" ≠ "Hänger werden
  erkannt".

## ACCEPTANCE_REQUIREMENT

- K1: Jede ARBEITET-Anzeige trägt Liveness-Evidenz: Worker-ID, Alter des
  letzten Heartbeats ("vor N s"), Quelle (`/workers` + Zeitstempel).
  ARBEITET ohne Heartbeat-Alter ist ungültig.
- K2: Geschlossene Frische-Stufen statt binärer Anzeige:
  FRESH (< 60 s) / AGING (< 300 s, mit Hinweis "im Toleranzfenster") /
  OVERDUE (> 300 s, "Antwort überfällig — Quarantäne steht aus/läuft").
  Kein ewiges ARBEITET nach OVERDUE.
- K3: Die stale-Erkennung selbst ist Evidenz: "Watchdog aktiv
  (letzter Reclaim-Lauf <Zeit>, Ergebnis <n quarantiniert>)" vs. ehrlich
  "KEINE stale-Erkennung aktiv — tote Worker werden nicht erkannt".
  Ohne Watchdog-Nachweis kein implizites Vertrauen in ARBEITET.
- K4: Nach Quarantäne zeigt der Task `HUMAN_REQUIRED` + `recovery_reason`
  + konkrete Next-Option (Resume/Retry-Pfad, Verweis auf B-Liste) —
  nicht nur BLOCKED ohne Erklärung.
- K5: Anti-False-Alarm: Legitim langsame Tasks (> 300 s Laufzeit) bleiben
  FRESH/AGING, solange Heartbeats eingehen. Heartbeat = "lebt",
  Fortschritt = separates Signal (siehe E). Beides wird getrennt gezeigt.

## MISSING_SYSTEM_SUPPORT

- Kein Frische-Urteil im Runtime-Code (nur rohe `last_seen`-Werte).
- Keine Watchdog-Liveness (kein eigener Heartbeat, kein `last_reclaim_at`,
  kein Ergebnis sichtbar).
- Kein OVERDUE-Signal vor/nach Quarantäne an der Task-Anzeige.
- Toter `reclaimed_tasks`-Zweig (K-d) an Code-Owner: entfernen oder echt
  befüllen.

## PREPARABLE_NOW

- Dieses Dokument (K1–K5 + Befunde K-a bis K-e).
- Ableitungsregel-Entwurf (deterministisch aus heutigem State):
  `age = now - worker.last_seen` → Stufe nach K2; Stufe OVERDUE +
  Step DISPATCHED + kein Watchdog-Nachweis → Warnung K3.
- K-a-Hinweis an Run-Prep-Owner: RUN/Pilot-Checklisten müssen
  "Watchdog läuft (PID/Log-Nachweis)" als Precondition enthalten,
  sonst ist jede ARBEITET-Anzeige ungedeckt.

## BLOCKED_UNTIL

- Echte Heartbeat-/Watchdog-Beobachtung erst mit physischem RUN/Pilot.
- Runtime-Owner implementiert Frische-Urteil + Watchdog-Liveness
  (nicht dieses Fenster).

## NEXT

L (Kosten-Transparenz): was kostet mich dieser Lauf — Spend-Meter,
Cap und Subscription-first-Nachweis statt nur `cost_class`-Labels.
