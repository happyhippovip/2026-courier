# User Acceptance U — Fehler-Texte / Melden-mit-Next (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: C-nah (Failure) + T-nah (Vokabular) — was WÖRTLICH dasteht,
wenn etwas schiefgeht. T liefert die Wörter; U liefert die Sätze.

## USER_PROBLEM

Als Nutzer scheitert etwas und ich lese: "Invalid task or worker."
Was ist ungültig — Task oder Worker? Was tue ich jetzt — Retry,
warten, neu einreichen, Support? Die Meldung sagt den Fehler, aber nicht
die Klasse, nicht das Verdikt, nicht den nächsten Schritt.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

Fehler-Inventar `server/app.py` (vollständig gelesen, Stand dieser Session):
- 503: "Courier API key is not configured" (`:24`),
  "Courier verifier authority is not configured" (`:40`),
  "planner failed: {exc}" (`:124`), "planner returned no actionable
  tasks" (`:127`).
- 401: "Unauthorized" (`:27`), "Verifier authority required" (`:42`).
- 400: "worker_id is required", "goal_text is required", "independent
  verifier_id is required", "result_id mismatch",
  "artifact evidence mismatch", "verdict must be PASS or FAIL",
  "Invalid task or worker", "Task cannot be resumed from status X",
  "force_success is not supported; retry and verify instead",
  "Unknown action", rohe ContractError-/ArtifactError-Texte.
- 404: "Unknown worker", "Unknown goal", "Unknown task", "Task not found".
- 409: "Task already reconciled", "Task has no result awaiting
  verification", "Conflicting result for already processed task",
  "Task is not awaiting a result".
- BEFUND U-a (genau eine vorbildliche Meldung): Nur
  "force_success is not supported; retry and verify instead" nennt
  Fehler + Next. Alle ~20 anderen: bloßer String — keine
  Failure-Klasse (C1), kein Retry-Verdikt (C2), keine Evidenz-Refs,
  kein Next.
- BEFUND U-b (Exception-Leak): "planner failed: {exc}" (`:124`)
  interpoliert beliebigen Exception-Text in die Nutzer-Antwort —
  instabile Wortlaute, mögliche Interna, kein T1-Glossar-Wort.
- BEFUND U-c (mehrdeutige Meldungen): "Invalid task or worker" (welches
  von beiden?), "Unauthorized" (falscher Key? fehlender Header? welcher
  Key?), "Task is not awaiting a result" (Retry sicher? abwarten?
  aufgeben? — C-Vakuum im häufigsten 409).
- BEFUND U-d (Sprach-Regel fehlt): Alle Meldungen Englisch, alle
  Nutzer-Docs dieser Reihe Deutsch. Keine Regel, welche Sprache die
  Anzeige-Schicht spricht — und ob Meldungen 1:1 durchgereicht oder
  gemappt werden.

## ACCEPTANCE_REQUIREMENT

- U1: Jede Fehlermeldung folgt dem Satz-Bau: WAS (T1-Wort) + KLASSE
  (Failure-Klasse nach C1) + VERDIKT (C2: SAFE_RETRY / RETRY_WITH_LIMITS
  / NEEDS_DECISION / FORBIDDEN) + NEXT (konkreter Schritt oder B-Listen-
  Verweis) + REFS (goal/task/attempt/dispatch-IDs). Fünf Teile, kein Teil
  fehlt ohne "[NICHT ERFASST]"-Markierung.
- U2: U-b-Fix (Runtime-Owner): Kein roher Exception-Text erreicht den
  Nutzer. Intern: volle Exception ins Server-Log (mit Korrelations-ID);
  außen: stabile Meldung + Korrelations-ID ("Fehler PL-1234, Details im
  Support-Bundle nach H1").
- U3: U-c-Fix durch Mapping-Tabelle (Prep, dann Code): Jede der ~20
  Meldungen erhält Klasse + Verdikt + Next. Beispiele: "Task is not
  awaiting a result" → Klasse STALE_RESEND, Verdikt NEEDS_DECISION bei
  neuem Result / SAFE_RETRY-nicht-nötig bei Duplikat (ACK_DUPLICATE-
  Pfad prüfen), Next "Result-Status abgleichen"; "Invalid task or
  worker" → aufspalten in zwei Meldungen mit je eigenem Next.
- U4: Status-Code-Disziplin: 400 = deine Anfrage ist falsch (Next: Payload
  fixen), 401 = Auth fehlt/falsch (Next: Key-Check nach F4), 404 =
  ID unbekannt (Next: ID prüfen/Neu einreichen), 409 = Wahrheits-Konflikt
  (Next: NIEMALS blind retryen — C4-Regel), 503 = Server-Seite nicht
  bereit (Next: warten + K-Frische prüfen). Der Code trägt die erste
  Next-Entscheidung, der Text die zweite.
- U5: Sprach-Regel (Prep-Entscheidung, Spec-Owner): Anzeige-Schicht
  spricht GENAU EINE Sprache pro Nutzer (Default: Nutzer-Sprache,
  Fallback Englisch); Server-Strings werden gemappt, nie roh gezeigt.
  Bis entschieden: U-d steht sichtbar im Glossar-Anhang (T), kein
  stilles Mischen.

## MISSING_SYSTEM_SUPPORT

- Kein Fehler-Satz-Bau im Code (nur Strings + Codes).
- Keine Mapping-Tabelle Meldung → Klasse/Verdikt/Next.
- Kein Korrelations-ID-Mechanismus, keine Sprach-Regel.

## PREPARABLE_NOW

- Dieses Dokument (U1–U5 + Befunde U-a bis U-d + Voll-Inventar oben).
- Mapping-Tabellen-Entwurf (alle ~20 Meldungen × Klasse/Verdikt/Next
  als Doku — U3-Vorarbeit, kein Code).
- U2/U5-Notizen an Runtime-/Spec-Owner.

## BLOCKED_UNTIL

- Echte Fehler-Texte-Evaluierung erst mit Pilot (welche Meldungen sehen
  Nutzer wirklich, welche fehlen in der Tabelle).
- Runtime-Owner baut Satz-Bau + Korrelations-IDs.

## NEXT

V (Zeitzonen-/Uhren-Disziplin): welche Uhr gilt — Heartbeat-Alter,
Stale-Schwellen und Zertifikats-Zeiten über Rechnergrenzen hinweg.
(K/O/S brauchen Zeiten; V definiert, welche Uhr sie liefert.)
