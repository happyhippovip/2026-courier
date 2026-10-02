# User Acceptance I — Pilot Feedback (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.

## USER_PROBLEM

Als Pilot-Nutzer weiß ich nicht: wie gebe ich Feedback, das als Signal
zählt? Reicht "lief gut"? Wer misst Setup-Zeit, Kosten, Interventionen —
und woher weiß ich, ob mein Feedback die Freischaltung beeinflusst?

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Metriken sind definiert (`PILOT_METRICS_AND_SIGNAL_SPEC.md`, GQ46):
  T_setup, HIPG, RSR, NDR, Support Effort, Provider Cost Class, TTUR.
- Signal-Schwellen sind definiert (GQ47): GREEN (RSR>80%, HIPG=0, NDR=100%,
  Diff appliable, Tests grün) / YELLOW (Courier ok, Provider halluziniert) /
  RED (HIPG>0 oder NDR<100% oder Verifier-Fehlakzeptanz oder Crash ohne
  Recovery). Nur GREEN entsperrt die Product Shell (GQ48).
- Gate bleibt LOCKED: `scripts/check_pilot_readiness.py` prüft nur
  Datei-Anwesenheit und sagt explizit, das Gate bleibe zu bis zum
  physischen Signal. Reuse-Befund: Datei-Check ≠ Signal.
- `PILOT_DUMMY_TASK.json` existiert (goal-pilot-001, human_relay_limit 0).
- OFFEN (Blocker für ehrliche Messung): T_setup-Ziel < 5 Min (GQ46) vs.
  `setup_time_minutes_max: 15` (Dummy-Task). Solange beide Zahlen gelten,
  ist jede Setup-Zeit-Messung uninterpretierbar.
- Es gibt keinen Feedback-Kanal: kein Formular, kein Store, keine
  Mess-Hooks für T_setup/HIPG/Kosten, keine Methode pro Metrik
  (wer misst was, womit, wann).

## ACCEPTANCE_REQUIREMENT

- I1: Jeder Pilot-Feedback-Record enthält: goal/task-Refs, Candidate-SHA,
  beobachtete Metriken (T_setup, HIPG, RSR, NDR, Kosten-Klasse, TTUR,
  Support-Aufwand) + Messmethode je Metrik + Freitext + Nutzer-Verdikt.
- I2: Messmethoden sind festgeschrieben: T_setup (Fetch→Worker-pollt,
  Zeitstempel), HIPG (gezählte manuelle Eingriffe mit B-Listen-Refs),
  NDR (Attempt-/Dispatch-Zählung aus State), Kosten (Provider-Abrechnung
  oder Zähler × Satz, Methode genannt).
- I3: Feedback entsperrt NICHT automatisch die Shell. Entsperrung braucht:
  GREEN-Metriken + unabhängige Evaluierung (nicht der Pilot-Nutzer allein)
  + J-Checkliste. Feedback ist Input, kein Schlüssel.
- I4: YELLOW/RED-Feedback verlangt eine Root-Cause-Klasse
  (Provider-Halluzination / Courier-Defekt / Setup-/Key-Problem /
  Umgebungs-Problem / UNKNOWN-mit-Evidenz). "Lief schlecht" ohne Klasse
  ist kein verwertbares Signal.
- I5: Bis zur 5-vs-15-Klärung (siehe F3) wird T_setup roh berichtet
  (Minuten + Methode), ohne Grün/Rot-Färbung.

## MISSING_SYSTEM_SUPPORT

- Kein Feedback-Store/Schema, keine Mess-Hooks, keine Methoden-Spec
  pro Metrik im Runtime-Code.
- Keine unabhängige Evaluierungs-Fläche (Prozess, kein Tool nötig).

## PREPARABLE_NOW

- Dieses Dokument (I1–I5 + Methoden-Skizzen in I2).
- Feedback-Record-Schema-Entwurf aus I1 (Felder als JSON-Spec, kein Code).
- Klär-Anfrage an Spec-Owner: eine T_setup-Zahl (5 oder 15).

## BLOCKED_UNTIL

- Echter Pilot-Run (erste echte Messwerte).
- T_setup-Ziel-Entscheidung durch Spec-Owner.

## NEXT

J (Product-Shell Acceptance): Wann ist die Shell freigeschaltet und was
muss sie mindestens können — Checkliste, zero Implementierung.
