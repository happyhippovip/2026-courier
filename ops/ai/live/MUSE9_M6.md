# MUSE9 M6 — timeout/kill/reap/exit-code/FAILED-Stickiness (Sidecar, READ_ONLY_C2)

Kein RUN, keine Revalidierung.

## Reuse zuerst
- `ops/ai/M1_M9/M6_PROCESS_REAP_TIMEOUT.md` (HIGH bestaetigt).
- `windows daemon.py:221-260` (run_task, Re-Read Refute-Stand); `app.py:390-407` (FAILED-Pfade, Refute-Stand).

## Subcases
- M6-S1 Kein Kill bei Timeout: `communicate(timeout=600)` + blankes
  `except → FAILED`, null Kill-Primitiven im File. Kind lebt weiter.
  Follow-up-Re-Probe (`:235-247`, +Timing-Zeilen): weiter kein Kill — HIGH REBESTAETIGT.
  Nebenbei: result_id-Schema + Timing-Felder umgearbeitet (ungesichtetes Delta, → M9-7).
  VERDIKT: CONFIRMED (HIGH steht).
- M6-S2 Exit-Code-Mapping: rc==0 → SUCCESS sonst FAILED; Exception (inkl.
  Timeout) → FAILED mit stderr-Text. VERDIKT: CONFIRMED.
- M6-S3 FAILED-Stickiness: FAILED klebt NICHT — attempts<3 → QUEUED (Retry `:390-393`);
  terminal erst bei attempts≥3 (FAILED_TERMINAL `:394-395`) bzw. Verify-FAIL (BLOCKED `:517-518`).
  Was "klebt", ist HUMAN_REQUIRED (braucht `resume`) — per Design.
  DRIFT (Zweit-Refute): attempts zaehlt DOPPELT (Claim `:323` + FAILED-Result `:393`) → effektiv 2 statt 3 Versuche. Disposition: Server-Owner (beabsichtigt?).
  VERDIKT: DISPROVEN ("FAILED-Wedge"); CONFIRMED (Retry-Progression + Quarantaene-Design + Doppelzaehlung).
- M6-S4 Reap-Luecke: Timeout-Pfad wartet/killt nie → kein Reap bis Daemon-Ende
  (Zombie nach Child-Exit; GC reapt NICHT — Praezisierung nach Selbst-Widerlegung).
  Handle-Leak minor. VERDIKT: CONFIRMED (per Abwesenheit im Code).
- M6-S5 Doppel-Effekt-Fenster: Retry waehrend Vorgaenger lebt (M6-S1 × M6-S3).
  Mechanismus sicher; konkrete Instanz nie beobachtet.
  VERDIKT: CONFIRMED (Mechanismus); MISSING_EVIDENCE (Instanz).

## OUTPUT
ROLE=M6
CONFIRMED=M6-S1 (HIGH, kein Kill); M6-S2 (Mapping); M6-S3-Retrypfad; M6-S4 (Reap-Leak); M6-S5-Mechanismus
DISPROVEN="FAILED klebt / Wedge"; "Timeout toetet den Task"; "Retry ist effekt-sicher"
MISSING_EVIDENCE=Beobachtete Doppel-Effekt-Instanz (darf es nie geben — Verbot, kein Wunsch)
OWNER_PACKET=Daemon-Owner: Kill-Tree bei Timeout + PID/create_time-Bindung (M6.3); bis dahin M6.2-Warntext vor Retry
CRITICAL_PATH=M6-S1/S5 → M9 BEFORE_RUN1 (Fix ODER Risiko-Akzeptanz VOR retry-lastigen Beweisen)
NEXT_OWNER=Daemon-Owner (Fix); Gate-Owner (Akzeptanz-Entscheid)
DO_NOT_REPEAT=Kill selbst implementieren (fremde Lane, Prep-only); Timeout-Zahlen ohne Messung drehen
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M6
SURVIVING_CONFIRMED=M6-S1 (HIGH, re-probt); M6-S2; M6-S3; M6-S4 (praezisiert); M6-S5
REMOVED=Nichts (S4-Praezisierung, kein Befund entfernt)
MINIMUM_NEXT_ACTION=Kill-Tree-Fix ODER Risiko-Akzeptanz (unveraendert); Daemon-Rework sichten (→ M9-7)
MINIMUM_TEST_OR_EVIDENCE=Owner-Entscheid (kein Test noetig)
NEXT_OWNER=Daemon-Owner
STATUS=DONE_STATIC
