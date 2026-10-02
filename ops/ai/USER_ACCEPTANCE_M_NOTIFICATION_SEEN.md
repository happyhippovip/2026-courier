# User Acceptance M — Benachrichtigung / Gesehen-Nachweis (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: B-nah ("Braucht dich" nützt nichts, wenn der Nutzer es nicht
erfährt, ohne ständig nachzusehen).

## USER_PROBLEM

Als Nutzer weiß ich nicht: erfahre ich es, wenn Courier mich braucht —
oder muss ich ständig selbst nachsehen? Und wenn ich es gesehen habe:
weiß Courier, dass ich es gesehen habe? Heute muss ich pollen, und
Gesehenes ist von Ungesehenem ununterscheidbar.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- `/walls` ist reines Pollen: gibt BLOCKED-Goals zurück
  (`server/app.py:171-179`), ohne Grund/Optionen/Deadline (B-Befund) und
  ohne jeden Gesehen-Status.
- Es gibt KEINEN Notify-/Push-/Webhook-/Subscribe-Mechanismus im
  Runtime-Code (Treffer für notif/webhook/push/alert/email/subscribe in
  `server/` + `scripts/`: nur fachfremde Experiment-Skripte
  (`inbound_response_observer.py`, `invoice_generator.py`) sowie
  agent-internes Snitch-Alert-Routing im Chief
  (`run_chief_commander.py:552-597`, Agent-zu-Agent, kein User-Kanal)).
- Es gibt kein "ungelesen"-Konzept: kein `seen`-/`acknowledged`-Feld an
  Goals/Tasks/Walls im State, kein Quittungs-Endpoint. Eine B-Liste nach
  Doc B erbt diese Lücke, solange M nicht umgesetzt ist.
- Einzige Liveness mit Zeitbezug sind Worker-`last_seen`-Werte
  (`server/app.py:209,243,265`) — für Worker, nicht für Human-Items.
- Positiv: HIPG=0 als Pilot-Normalfall (Doc B/I) begrenzt das Problem —
  im Normalpfad gibt es nichts zuzustellen. Jedes Braucht-dich ist damit
  ein seltenes, erklärungspflichtiges Ereignis, das Zustellung verdient.

## ACCEPTANCE_REQUIREMENT

- M1: Ehrlicher Poll-Vertrag bis Push existiert: "Courier benachrichtigt
  dich derzeit NICHT aktiv. Prüfe <Ort> alle <Intervall>." Intervall und
  Ort stehen an der B-Fläche, nicht im Kleingedruckten.
- M2: Jedes Braucht-dich-Item trägt einen Gesehen-Status:
  UNSEEN → SEEN (mit Zeitpunkt) → ANSWERED (mit Entscheidungs-Ref nach
  B5). UNSEEN altert sichtbar ("wartet seit N Stunden").
- M3: Kein stilles Verfallen: Ein UNSEEN-Eintrag bleibt offen, bis er
  beantwortet oder explizit zurückgezogen wird (mit Grund + Ref).
  Timeout-ohne-Entscheidung fällt auf den sicheren Default der B-Regel
  (B1) zurück UND bleibt als "per Default entschieden, Review offen"
  sichtbar.
- M4: Eskalations-Regel für Kritisches: MONEY-/SAFETY-Walls ohne SEEN nach
  <Schwelle> werden erneut vorgelegt (nicht lauter, nicht öfter als
  definiert — aber nie genau einmal und dann nie wieder).
- M5: Späterer Push-Kanal (nach Pilot, nicht jetzt) trägt dieselben IDs
  (goal/task/dispatch + Wall-ID): Push ist Zustellung, kein zweiter
  Wahrheitskanal. Bis dahin gilt M1, ohne Ausnahme.

## MISSING_SYSTEM_SUPPORT

- Kein Push-/Notify-Kanal (per Design: erst nach Pilot überhaupt denkbar).
- Kein Seen-/Ack-State, kein Quittungs-Endpoint, keine Alterungs-Anzeige.
- Keine Eskalations-/Verfalls-Regel im Runtime-Code.

## PREPARABLE_NOW

- Dieses Dokument (M1–M5 + Poll-Vertrag-Wording für sofort).
- M1-Wording als sofort verwendbare ehrliche Anzeige-Regel:
  "Aktive Benachrichtigung: AUS (Prep-Phase). Ungelesene Punkte: <n>,
  ältester seit <Zeitpunkt>."
- Seen-State-Schema-Entwurf (Felder: wall_id, state UNSEEN/SEEN/ANSWERED,
  seen_at, seen_by, decision_ref) — Schema, kein Code.

## BLOCKED_UNTIL

- Echte Human-Items entstehen erst mit physischen RUNs / Pilot.
- Push-Entscheidung (M5) erst nach positivem Pilot-Signal.

## NEXT

N (Datenorte/Löschung): wo liegen meine Daten, was wächst unbegrenzt,
und wie lösche ich sie — Retention- und Vergessen-Regeln als Prep.
