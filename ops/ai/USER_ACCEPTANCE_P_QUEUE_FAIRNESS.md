# User Acceptance P — Warteschlange / Reihenfolge / Fairness (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: E-nah (Progress/Next) + L-nah (Deferral-Sichtbarkeit) — die
Warteschlange als eigene Nutzer-Fläche: was steht an, warum diese Reihenfolge.

## USER_PROBLEM

Als Nutzer weiß ich nicht: welche Aufgaben stehen an, in welcher
Reihenfolge werden sie bedient — und warum wartet meine Aufgabe, während
eine andere läuft? "Task: null" ist keine Erklärung, und "die Reihe
entscheidet" ist keine sichtbare Regel.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Claim-Bedienung: Goals in Dict-Reihenfolge (Erstellungs-Reihenfolge),
  pro Goal nur der Head-Step (`current_step_index`, nur wenn QUEUED),
  nur bei Capability-Match (`server/app.py:270-282`). Kein
  Prioritäts-Feld, keine Fairness-Regel, keine Umgehung blockierter Heads
  nötig (Schleife läuft weiter — gut).
- ABER — Befund P-a (stumme Leere): Leerer Claim antwortet mit bloßem
  `{"task": null}` (`:343`) — ohne Grund. Queue-leer, kein
  Capability-Match, Deferral für billigeren Worker (L-b) und
  alles-blockiert sind ununterscheidbar. (Präzedenz für Gründe existiert:
  `WORKER_BUSY`, `:268`.)
- Befund P-b (starre Reihenfolge): Bei knapper Worker-Kapazität gewinnt
  immer das älteste ACTIVE-Goal. Kein Priorisieren, kein "diese Aufgabe
  zuerst", keine Fairness-Garantie für später erstellte Goals. Für 1
  Worker + 2 Goals heißt das: Goal 2 wartet, bis Goal 1 komplett durch
  ist — ohne dass das irgendwo stünde.
- Befund P-c (unsichtbare Tiefe): Nicht-Head-Steps haben keine
  sichtbare Position ("Schritt 5 von 8, 2 davor in Arbeit/vormerkbar").
  Der Nutzer sieht QUEUED-Steps nur als Liste ohne Ordnungssinn.
- Positiv: Single-Head-Gating macht B-legal deterministisch (Z06-Befund);
  die Regel ist simpel und erklärbar — sie wird nur nirgends erklärt.

## ACCEPTANCE_REQUIREMENT

- P1: Jeder leere Claim trägt einen Grund (geschlossenes Vokabular):
  QUEUE_EMPTY / NO_CAPABILITY_MATCH / DEFERRED_FOR_CHEAPER /
  ALL_HEADS_BLOCKED / WORKER_BUSY (bestehend). Leere ohne Grund ist
  ungültig. (P-a-Fix.)
- P2: Die Bedien-Reihenfolge ist angezeigt: "Goals werden in
  Erstellungs-Reihenfolge bedient, je Goal ein Schritt zur Zeit."
  Solange keine Priorisierung existiert, steht die Default-Regel sichtbar
  an der Queue-Fläche — kein implizites Wissen. (P-b-Doku.)
- P3: Fairness-Regel für später (Prep, kein Bau): Wenn Priorisierung kommt,
  dann als explizites Goal-Feld mit Default (Erstellungs-Reihenfolge),
  nie als stille Sonderlogik. Starvation-Wächter: Kein ACTIVE-Goal wartet
  länger als <Schwelle>, ohne dass die Anzeige sagt, warum.
- P4: Queue-Position pro Step: "Schritt k von n, Head in <Status>,
  voraussichtlich als Nächstes: <ja/nein + Grund>". Keine ETA-Zahl ohne
  Messbasis (E-Regeln), aber Ordnungssinn statt QUEUED-Einheitsbrei.
- P5: Deferral erscheint in der Queue-Sicht: "zurückgestellt — wartet auf
  billigeren Worker (L4)". Kosten-Entscheidungen sind Queue-Ereignisse,
  keine unsichtbaren Claim-Interna.

## MISSING_SYSTEM_SUPPORT

- Kein Claim-Grund bei Leere (P-a), keine Queue-Sicht, keine Position.
- Kein Prioritäts-Feld, keine Fairness-Metrik, kein Starvation-Wächter.
- Keine Deferral-Ereignisse (siehe auch L4).

## PREPARABLE_NOW

- Dieses Dokument (P1–P5 + Befunde P-a bis P-c).
- Grund-Vokabular P1 als sofort übernehmbarer Enum-Vorschlag
  (ein-Zeilen-Fix-Kandidat an Code-Owner: `{"task": None, "reason": ...}`).
- P2-Wording als sofort ehrliche Queue-Regel-Anzeige.

## BLOCKED_UNTIL

- Echte Multi-Goal-Last erst mit Pilot (Fairness-Fragen werden dann real).
- Runtime-Owner implementiert Claim-Gründe + Queue-Sicht.

## NEXT

Q (Kapazitäts-/Worker-Sicht): welche Worker sind da, was können sie,
sind sie ausgelastet oder weg — `/workers`-Rohdaten als Nutzer-Fläche.
(K liefert Frische; Q liefert Bestand + Fähigkeiten + Auslastung.)
