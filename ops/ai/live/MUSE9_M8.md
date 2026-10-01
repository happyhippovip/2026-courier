# MUSE9 M8 — RUN_2 restart/no-A-replay/stale-result/stale-worker (Sidecar, READ_ONLY_C2)

KEIN RUN. Witness-Specs + Code-Mechanik (gelesen) vs Harness-Brueche (gelesen).

## Reuse zuerst
- `ops/ai/M1_M9/M8_RUN2_NO_REPLAY.md` (M8-1..M8-4 — hier NICHT wiederholt).
- `app.py:195-202` (Restart-Quarantaene), `:359-373` (Resend/409), `:419-458`
  (Reclaim); `windows daemon.py:317-328,365-380`; `run_2_mac.sh`, `verify_run2_evidence.py`. (Refs Refute-Stand.)

## Subcases
- M8-S1 A-bleibt-RECONCILED: W1 = Vor/Nach-State-Snapshot von A identisch
  (Status + result_id + verification); W2 = kein neuer attempt/dispatch fuer A.
  Spec: CONFIRMED. Evidenz: MISSING.
- M8-S2 No-A-Replay: W1 = attempt-Zaehler unveraendert; W2 = kein zweiter
  Effekt-Artefakt; W3 = kein zweiter dispatch. Log-Substring-Methode des
  Checkers (`:37`) ist vakuos (Strings kommen nie vor → besteht auch bei
  Stillstand). VERDIKT: Spec CONFIRMED; Checker-Methode DISPROVEN.
- M8-S3 Stale-Result nach Restart (Trichotomie, Code): CLAIMED → lokaler Re-Run
  (Effekt begann nie; kein Server-Reclaim — Praezisierung nach Selbst-Widerlegung);
  STARTED → Quarantaene statt Replay; RESULT_READY → Redelivery + ACK_DUPLICATE
  bei Exaktheit. VERDIKT: CONFIRMED (Code).
- M8-S4 Stale-Worker in RUN2: toter Worker + DISPATCHED-B → Quarantaene, B
  braucht `resume retry` (Mensch). Kein Auto-Requeue. VERDIKT: CONFIRMED (Code).
- M8-S5 B-reconciled: Spec wie M7-S1..S3 (CONFIRMED); Harness-DB-Namens-Bruch
  (`ledger_run1.db` vs Checker-`ledger_run2.db`) CONFIRMED-GAP (M8-1).
- M8-S6 Kill-Methode: `kill -9`+Port-Check passt nur Flask-dev; gunicorn-Pfade
  ungebunden; B-Definition fehlt. VERDIKT: MISSING_EVIDENCE = Entscheidung fehlt,
  BLOCKED_OTHER_OWNER (RUN-Lane).

## OUTPUT
ROLE=M8
CONFIRMED=S1/S2/S5-Specs; S3-Trichotomie; S4-Quarantaene; S5-DB-Bruch (Gap); Checker-Vakuitaet
DISPROVEN="Log-Abwesenheit beweist No-Replay"; "RUN2-wie-geskriptet beobachtet irgendetwas"
MISSING_EVIDENCE=Alle RUN2-Evidenzen; Kill-Methoden-Entscheid; B-Definition
OWNER_PACKET=RUN-Lane: M8.1-Reparatur (`M8_RUN2_NO_REPLAY.md`) + Entscheide (dev-vs-gunicorn, B-Task) + Witness-Checkliste S1/S2/S5
CRITICAL_PATH=S6-Entscheide + M8.1 → M9 BEFORE_RUN2; S1/S2/S5 → M9 RUN2_EVIDENCE
NEXT_OWNER=RUN-Harness-Owner; Mac-Operator
DO_NOT_REPEAT=M8-1..M8-4 neu erzaehlen; Restart-Semantik neu beweisen (M5 steht); RUN starten
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M8
SURVIVING_CONFIRMED=M8-S1/S2 (Specs; Checker-Methode weiter DISPROVEN); M8-S3 (praezisiert); M8-S4/S5
REMOVED=Nichts
MINIMUM_NEXT_ACTION=M8.1 + Kill-/B-Entscheide (unveraendert)
MINIMUM_TEST_OR_EVIDENCE=RUN2-Evidenzen nach Reparatur (RUN-Lane)
NEXT_OWNER=RUN-Harness-Owner
STATUS=DONE_STATIC
