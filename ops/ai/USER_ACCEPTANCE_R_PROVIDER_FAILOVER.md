# User Acceptance R — Provider-Ausfall / Übernahme / Wechsel (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: C-nah (Failure) + Q-nah (Kapazität) — was der Nutzer bei
Provider-Ausfall sieht, wer übernimmt, was verloren geht.

## USER_PROBLEM

Als Nutzer weiß ich nicht: wenn mein Provider (Modell/Worker) ausfällt —
wer übernimmt meine Aufgabe? Läuft sie woanders weiter, startet sie neu,
oder bleibt sie liegen, bis ich eingreife? "Resilient" ist ein Wort;
ich brauche den Ablauf.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Worker-gemeldete Fehlschläge werden automatisch neu eingereiht: FAILED-
  Result mit attempts < 3 → QUEUED + Worker freigegeben
  (`server/app.py:385-387`); erst der 3. Fehlschlag → FAILED_TERMINAL +
  BLOCKED (`:389,400-401`). Retrybar per resume (`:531-545`).
- Stale-Worker (Heartbeat weg) werden NICHT neu eingereiht, sondern
  quarantäniert: HUMAN_REQUIRED + STALE_WORKER_EFFECT_AMBIGUOUS + BLOCKED
  (`:427-446`) — Effekt-Ambiguität schlägt Auto-Replay. Begründet,
  aber: Niemand übernimmt automatisch.
- BEFUND R-a (Doku-vs-Code, GQ44): `PILOT_METRICS_AND_CONTRACT.md`
  verspricht: "server reassigns the task to another healthy provider of
  matching capabilities". Im Dispatch-Code existiert KEIN
  Reassign-/Failover-Pfad (null Treffer für reassign/failover/migrate/
  takeover/fallback in `server/`; einziger verwandter Treffer ist
  fachfremder Bodyguard-Standby-State). Was GQ44 verspricht, tut der
  Code nicht — der Code quarantäniert und wartet auf den Menschen.
- BEFUND R-b (kein Provider-Gedächtnis): Retry setzt `worker_id` zurück
  (`:386-387`), der nächste Claimant kann derselbe wackelige Provider
  sein (solange er heartbeated). Kein Ausschluss nach Fehlschlag, kein
  Backoff, keine Denylist. Ein flatternder Provider kann denselben Task
  wiederholt ziehen und wiederholt fehlschlagen — bis FAILED_TERMINAL.
- BEFUND R-c (kein Übernahme-Protokoll): Es gibt keine sichtbare
  "Übernahme"-Erzählung (von Worker A an Worker B, Versuch k, Grund).
  Der Nutzer sieht Status-Sprünge (DISPATCHED → QUEUED → DISPATCHED),
  nie "Provider X fiel aus, Task liegt bei Y wieder vor".

## ACCEPTANCE_REQUIREMENT

- R1: Ehrliche Ausfall-Anzeige pro Fall: Worker-Fehler (Versuch k/3,
  auto-requeued) vs. Provider-stale (quarantäniert, braucht Entscheidung)
  vs. terminal (alle Versuche verbraucht). Drei Fälle, drei Anzeigen,
  keine Vermischung.
- R2: R-a wird dispositioniert (Spec-Owner): Entweder GQ44-Versprechen
  streichen ("kein Auto-Failover; Quarantäne + Human-Resume ist das
  Design") oder Failover implementieren. Bis dahin zeigt jede
  Resilienz-Fläche: "Auto-Übernahme: NICHT IMPLEMENTIERT — Ausfall führt
  zu Quarantäne + Braucht-dich (B-Liste)."
- R3: Retry trägt Provider-Historie: "Versuch 2/3, Versuch 1 lief bei
  Worker X (<Grund>), jetzt bei Y". Wiederholter Fehlschlag desselben
  Providers am selben Task wird sichtbar (R-b-Transparenz als erster
  Schritt; Ausschluss-Regel später).
- R4: Spätere Ausschluss-Regel (Prep, kein Bau): Provider nach N
  Fehlschlägen am selben Task für diesen Task sperren (mit Grund +
  Entsperr-Regel). Kein ewiger Flatter-Loop bis FAILED_TERMINAL.
- R5: Kein stiller Verlust: Jede Übernahme-/Quarantäne-Entscheidung nennt
  den Verbleib des Effekts ("Ergebnis des toten Versuchs: unbekannt —
  deshalb kein Replay", Verweis auf C-Verdikt). Der Nutzer erfährt, WARUM
  nicht einfach neu gestartet wurde.

## MISSING_SYSTEM_SUPPORT

- Kein Failover/Reassign-Pfad (per Design Quarantäne — aber GQ44
  widerspricht, siehe R2).
- Kein Provider-Gedächtnis, kein Ausschluss, kein Backoff.
- Kein Übernahme-Protokoll, keine Retry-Historie mit Provider-IDs.

## PREPARABLE_NOW

- Dieses Dokument (R1–R5 + Befunde R-a bis R-c).
- R2-Klär-Anfrage an Spec-Owner (GQ44 streichen vs. Failover bauen).
- Anzeige-Wording für sofort: Ausfall-Fall + Verbleib + Next (R1/R5).

## BLOCKED_UNTIL

- Echte Provider-Ausfälle erst mit Pilot (mehrere Provider, echte Last).
- Spec-Owner dispositioniert R2; Runtime-Owner baut Historie/Regeln.

## NEXT

S (Erst-Task/Probe-Goal): womit fange ich als neuer Nutzer an — welches
kleine Goal beweist mir, dass mein Setup funktioniert, bevor ich echte
Arbeit anvertraue? (Canary für den Nutzer, nicht für die Pipeline.)
