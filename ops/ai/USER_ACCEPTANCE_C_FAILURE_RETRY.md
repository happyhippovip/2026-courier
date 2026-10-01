# User Acceptance C — Failure / Retry / Restart (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.

## USER_PROBLEM

Als Nutzer sehe ich nicht: was ist kaputt — und darf ich gefahrlos Retry
oder Restart drücken? Die Angst: ein Retry löst den Effekt doppelt aus
(Kosten, Doppelschreibzugriff), ein Restart verliert ein akzeptiertes Result.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

Server-Seite (Code vorhanden, physisch UNPROVEN aus diesem Fenster):
- Idempotente Result-Annahme: identische Duplicates → ACK_DUPLICATE (200),
  widersprüchliche → 409, stale → kein Überschreiben der Wahrheit.
- `force_success` wird verweigert (400, "retry and verify instead").
- `/tasks/reclaim_stale` und `/tasks/<id>/resume` existieren;
  Transport-Retry vs. Re-Execution sind im Design getrennt.
- Restart-Matrix (Gate 4, kanonischer Plan): 9 Szenarien, Ziel RSR=100%.
  Status: NOT_PROVEN, PREP_ONLY. RUN_2 (Restart-Beweis) steht aus.
- Kein nutzerlesbares Retry-Sicherheitsurteil existiert: keine
  Failure-Klasse, kein SAFE/UNSAFE-Verdikt, keine Evidenz-Referenz
  an der Fehlermeldung.

## ACCEPTANCE_REQUIREMENT

- C1: Jede Failure-Anzeige enthält: Failure-Klasse, Retry-Verdikt,
  Begründung in einem Satz, Evidenz-Refs (goal/task/attempt/dispatch/result).
- C2: Geschlossenes Retry-Vokabular:
  SAFE_RETRY (idempotent belegt) / RETRY_WITH_LIMITS (z. B. max N, nur
  Transport-Retry) / NEEDS_DECISION (geht an B-Liste) / FORBIDDEN
  (Retry würde Doppelwirkung oder Wahrheitsverlust riskieren).
- C3: Restart-Zusage, sobald Gate-4-Evidenz vorliegt: akzeptiertes Result
  bleibt erhalten, RECONCILED wird nie erneut dispatched, nächste Aktion
  ist deterministisch. Vorher heißt die ehrliche Anzeige: RESTART_UNPROVEN.
- C4: Retry wiederverwendet Identitäten (gleiche dispatch/attempt-IDs für
  Transport-Retry); ein neuer Attempt wird nur für echte Re-Execution
  gemünzt und als solche gekennzeichnet.
- C5: Verbotenes blindes Verhalten: keine stille Doppelwirkung, kein
  stilles Verwerfen eines akzeptierten Results, kein Retry-Loop ohne Limit.

## MISSING_SYSTEM_SUPPORT

- Kein Failure-Taxonomie-Mapping von Server-Fehlern auf C2-Verdikte.
- Keine Restart-Zusagen-Anzeige (hängt an ausstehendem RUN_2-Beweis).
- Kein Retry-Limit-/Zähler-State, der dem Nutzer sichtbar wäre.

## PREPARABLE_NOW

- Dieses Dokument (Klassen + Verdikt-Regeln C1–C5).
- Verdikt-Regeltabelle aus bestehender Server-Semantik ableiten
  (ACK_DUPLICATE→SAFE_RETRY bei Transportfehlern; 409→NEEDS_DECISION;
  force_success→FORBIDDEN mit Verweis auf retry-and-verify).

## BLOCKED_UNTIL

- RUN_2 Restart-Beweis (C3-Zusage erst danach ehrlich möglich).
- Runtime-Owner mappt Fehler → Verdikte.

## NEXT

D (Proof/Verifikation): was wurde WIRKLICH verifiziert — synthetisch
vs. physisch, inkl. offener Zähl-/Scope-Diskrepanzen.
