# User Acceptance O — Fertig-Zertifikat / Verbindlicher Abschluss (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: E-nah (Progress/Next) + D-nah (Proof) — schließt die Lücke vom
Status-String zum belegbaren "fertig und geprüft".

## USER_PROBLEM

Als Nutzer sehe ich irgendwann "DONE" — aber ist das verbindlich fertig?
Was genau wurde geprüft, von wem, wann, mit welchem Ergebnis? Und umgekehrt:
Ein Goal steht seit Tagen auf BLOCKED — wartet es noch auf mich, oder ist
es faktisch aufgegeben? "Fertig" und "aufgegeben" sind heute beide
Ratesache.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- DONE ist stark (vertrauenswürdig): Ein Goal wird nur DONE, wenn jeder
  Step per unabhängigem Verify-PASS RECONCILED wurde und der Index das
  Plan-Ende erreicht (`server/app.py:502-507`). Kein Shortcut, kein
  `force_success` (`:546-549` verweigert). Gut.
- Terminale Failure-Pfade sind retrybar, nicht endgültig: 3. Fehlversuch
  → `FAILED_TERMINAL` + Goal BLOCKED (`:385-401`); FAIL-Verdikt →
  `FAILED_VERIFICATION` + BLOCKED (`:508-510`); stale-Quarantäne →
  `HUMAN_REQUIRED` + BLOCKED (`:430-446`). Alle drei sind per
  `/tasks/<id>/resume` (action=retry) requeu-bar (`:531-545`).
- ABER — Befund O-a (kein Abschluss-Beleg): Ein DONE-Goal trägt keine
  Kette (Step → Result → Verifier → PASS), keinen Zeitpunkt, keine Dauer.
  Goal- und Task-Records enthalten keine Timestamps (weder created_at noch
  completed_at). "Seit wann fertig, wie lange gedauert, wer hat was
  geprüft" ist aus dem State nicht beantwortbar.
- Befund O-b (kein Aufgegeben): Es gibt keinen ABANDONED/CLOSED-Status.
  Ein dauerhaft BLOCKED-Goal (kein Retry, keine Antwort) ist von "wartet
  aktiv auf mich" ununterscheidbar. Die B-Liste (Doc B) würde ewig alternde
  UNSEEN-Einträge zeigen (Doc M), ohne dass "aufgegeben" je ein Wort wäre.
- Befund O-c (Zähl-Lücke im Resume): Retry setzt Status zurück und mintet
  frische attempt/dispatch-IDs (`:534-545`), aber `resumed_from` ist die
  einzige Historie — kein Retry-Zähler, kein "2. Versuch von N". Der Nutzer
  sieht QUEUED, nicht "3. Anlauf nach 2 Fehlschlägen".

## ACCEPTANCE_REQUIREMENT

- O1: Jedes DONE-Goal erhält ein Fertig-Zertifikat (ableitbar, kein neuer
  Schreibpfad nötig): goal_id, Plan-Umfang (n/n Steps), pro Step
  (task_id, result_id, verifier_id, PASS, artifact-Refs), Abschlusszeit,
  Candidate-SHA, Proof-Level. DONE ohne Zertifikat ist ungültige Anzeige.
- O2: Zeit wird belegt, nicht geraten: Abschlusszeit + Dauer stehen im
  Zertifikat, sobald Runtime-Owner Timestamps persistiert (O-a-Fix).
  Bis dahin heißt die ehrliche Anzeige "Abschlusszeit: NICHT ERFASST
  (Pre-Timestamp-State)" — keine erfundene Dauer.
- O3: Aufgegeben ist ein expliziter Zustand: ABANDONED (wer gab auf, wann,
  warum, mit B-Listen-Ref) — vom Nutzer entschieden oder per Regel nach
  definierter Frist mit Ankündigung. BLOCKED altert nie still in
  Vergessenheit; O-b-Fix durch Runtime-Owner.
- O4: Retry-Historie ist sichtbar: "Versuch k (von max N), vorherige
  Versuche: <Gründe>". `resumed_from` wird zur Kette, nicht zur
  Ein-Zeilen-Notiz (O-c-Fix).
- O5: Das Zertifikat ist zitierbar: Hash oder ID, mit der ein Dritter
  (Support, Pilot-Evaluierung) genau dieses Fertig prüfen kann —
  Anker für D1-Evidenz-IDs und H5-Bundle-Refs.

## MISSING_SYSTEM_SUPPORT

- Keine Timestamps an Goals/Tasks/Steps/Verifications.
- Kein Zertifikats-Builder (ableitbar, aber nicht implementiert).
- Kein ABANDONED-Status, keine Aufgebe-Regel, kein Retry-Zähler.

## PREPARABLE_NOW

- Dieses Dokument (O1–O5 + Befunde O-a bis O-c).
- Zertifikats-Schema-Entwurf aus O1 (Felder als JSON-Spec, kein Code).
- O-a/O-b/O-c-Notizen an Runtime-Owner (Timestamps, ABANDONED, Zähler).

## BLOCKED_UNTIL

- Erstes echtes DONE-Goal aus physischem RUN/Pilot (Zertifikat füllen).
- Runtime-Owner persistiert Timestamps + ABANDONED.

## NEXT

P (Queue-Fairness/Sichtbarkeit): welche Aufgaben stehen an, in welcher
Reihenfolge, warum diese zuerst — Head-Step-Gating und Deferral für den
Nutzer erklärt. (Z06 B-legal + L-b legen vor; P macht die Warteschlange
als Nutzer-Fläche daraus.)
