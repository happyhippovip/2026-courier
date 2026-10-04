# User Acceptance S — Erst-Task / Probe-Goal / Selbsttest (Operator Window)

Status: PREP_ONLY (no Product Shell build; acceptance + observability prep only).
Date: 2026-09-28. Statische Befunde, keine physischen RUNs.
Priorität: F-nah (Onboarding) + D-nah (Proof) — der Canary für den NUTZER:
womit beweise ich mir selbst, dass mein Setup funktioniert, bevor ich echte
Arbeit anvertraue.

## USER_PROBLEM

Als neuer Nutzer weiß ich nicht: womit fange ich an? Gibt es ein kleines,
harmloses Probe-Goal, das mir Ende-zu-Ende zeigt "dein Setup funktioniert"
— was muss ich einreichen, was muss ich beobachten, und woran erkenne ich,
dass der Selbsttest bestanden ist? Heute gibt es Loader, aber keine
Landeanleitung.

## CURRENT_RUNTIME_TRUTH (belegt, statisch)

- Ein Probe-Artefakt existiert: `ops/ai/PILOT_DUMMY_TASK.json`
  (goal-pilot-001, windows-Target, 60-s-Timeout, human_relay_limit 0,
  Artifact mit fixer expected_sha256). Aber es ist Cohort-Infrastruktur,
  keine Nutzer-Anleitung: keine Einreich-Anweisung, keine
  Beobachtungs-Anweisung, keine Bestehens-Kriterien in Nutzersprache.
- F5 (Doc F) fordert den Bereitschaftsbeleg (Server antwortet, Worker
  pollt, SHA gebunden) — aber kein "reicht dieses Goal ein und verfolgt
  QUEUED → DISPATCHED → RESULT_RECEIVED → RECONCILED → DONE" als
  geführten Selbsttest.
- ABER — Befund S-a (staler Prüfer): `scripts/verify_pilot_task.py`
  verlangt Top-Level-Felder (task_id/attempt_id/dispatch_id/
  target_capability/instructions/expected_scope/worker_phase=PENDING),
  aber `PILOT_DUMMY_TASK.json` hat eine völlig andere Form
  (schema_version/goal_text/workflow_plan/pilot_metadata). Der Prüfer
  würde sein eigenes Artefakt als FAILED verwerfen. Statisch belegt
  durch Feldvergleich — kein Lauf nötig.
- Befund S-b (eingebaute Bestanden-Anzeige): `scripts/
  pilot_gate_readiness_check.py` druckt alle Metriken als PASS mit
  fest verdrahteten "actual"-Werten (2 Min, 0, 100 %, … — Literale in
  `:13-19`), ohne irgendetwas zu messen. Echt prüft es nur 3x
  Datei-Existenz (`:29-34`). Wer es laufen lässt, sieht PASS, ohne dass
  je etwas lief. (Verwandt zum I-Befund "Datei-Check ≠ Signal" — hier
  zusätzlich mit erfundenen Messwerten.)
- Befund S-c (Ziel-Widerspruch im Code bestätigt): Der Readiness-Check
  nutzt `SETUP_TIME_MAX_MINUTES target: 15` (`:13`) — passend zum
  Dummy-Task, im Widerspruch zu GQ46 (< 5 Min). Der F3/I5-Klärpunkt
  existiert damit auch als Code-Fakt, nicht nur als Doku-Diskrepanz.

## ACCEPTANCE_REQUIREMENT

- S1: Es gibt genau EIN dokumentiertes Probe-Goal ("Hello-Goal"): Payload
  (POST /goals, minimal), erwarteter Ablauf (Zustandsfolge + was der
  Nutzer wann sieht), erwartete Dauer (< N Min), Bestehens-Kriterien
  (DONE + Zertifikat nach O1 + HIPG=0). Kopierbar, ungefährlich,
  rückstandsfrei verwerfbar (N4).
- S2: Der Selbsttest misst, statt zu behaupten: Setup-Zeit, Time-to-DONE,
  Interventionen werden aus Timestamps/State abgeleitet (T_setup-Methode
  nach I2) — keine Literale, kein PASS ohne Lauf. (S-b-Fix.)
- S3: Jeder Prüfer passt zu seinem Artefakt: S-a wird gefixt (Prüfer an
  aktuelles Schema oder Artefakt an Prüfer — Entscheidung Runtime-Owner)
  oder der stale Prüfer wird entfernt/umbenannt. Ein Prüfer, der sein
  eigenes Artefakt verwirft, darf nicht unter produktivem Namen liegen.
- S4: Negativ-Pfad gehört zum Selbsttest: Der Nutzer sieht mindestens
  einmal bewusst einen Fehler (z. B. falscher Key → 401, oder Stop des
  Workers → OVERDUE nach K2) mit der zugehörigen Anzeige — damit er im
  Ernstfall die Signale wiedererkennt.
- S5: Bis S1 existiert, sagt Onboarding ehrlich: "Geführter Selbsttest:
  NOCH NICHT VERFÜGBAR — Setup endet derzeit mit manuellem
  Bereitschafts-Check (F5)." Kein Readiness-PASS ohne Lauf (S-b) als
  Ersatz.

## MISSING_SYSTEM_SUPPORT

- Kein Hello-Goal-Dokument, keine Selbsttest-Führung, keine Mess-Hooks.
- Staler Prüfer (S-a), irreführender Readiness-Check (S-b) im Baumbestand.
- Keine Timestamps für echte Selbsttest-Messung (siehe O-a).

## PREPARABLE_NOW

- Dieses Dokument (S1–S5 + Befunde S-a bis S-c).
- Hello-Goal-Skizze (Payload-Entwurf + Beobachtungs-Protokoll als Doku,
  kein Code): 1-Step-Plan, windows- oder linux-Target je Host,
  No-Op-Instruktion mit Artifact-Hash wie Dummy-Task.
- S-a/S-b-Notizen an Runtime-Owner (fixen oder deprecieren).

## BLOCKED_UNTIL

- Echter Selbsttest-Lauf erst mit physischer Umgebung (Server + Worker).
- Spec-Owner klärt 5-vs-15 (F3/I5/S-c) — der Selbsttest braucht EINE Zahl.

## NEXT

T (Verständnis-Check/Glossar-Disziplin): welche Wörter darf Courier dem
Nutzer zeigen — geschlossenes Anzeige-Vokabular gegen Freitext-Status
(A2/C2/K2/P1/Q3 legen vor; T zieht die Regel aufs ganze Produkt).
