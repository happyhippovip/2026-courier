# MUSE9 M7 — RUN_1 Proof Chain + unabhaengige Witnesses (Sidecar, READ_ONLY_C2)

KEIN RUN. Nur: Was muss RUN1 zeigen + welche UNABHAENGIGEN Zeugen bestaetigen je
Claim (mind. 2, verschiedene Quellen)?

## Reuse zuerst
- `ops/ai/M1_M9/M7_RUN1_PROOF_CHAIN.md` (8 Harness-Luecken — hier NICHT wiederholt).
- `server/app.py` (Claim/Result/Verify), `daemon.py` (Phasen), `artifact_store.py`,
  `central_state.json` (Q10-Spiegel-Lag beobachtet).

## Subcases (Claim → Witness-Paar → Stand)
- M7-S1 Genau-einmal-A: W1 = Server `attempts==1` + genau 1 dispatch_id;
  W2 = Daemon-Phasenfile (genau 1× CLAIMED→RESULT_READY, kein Re-CLAIM).
  Spec ableitbar: CONFIRMED. Evidenz: MISSING (kein RUN).
- M7-S2 Hash-Match: W1 = Server-Re-Hash (Artifact-Record); W2 = Verifier-
  unabhaengiger Re-Hash der Server-Kopie. Spec: CONFIRMED. Evidenz: MISSING.
- M7-S3 A-RECONCILED: W1 = Task-Status + Verification-Block (verifier≠worker,
  result_id-Gleichheit); W2 = Step-Spiegel im Workflow-Plan. Q10-Divergenz (Task
  RECONCILED / Step RESULT_RECEIVED) CONFIRMED beobachtet, aber ggf. HISTORISCH
  (alter Server-Stand, Baum mutiert) — untrennbar ohne Versionsstempel. Witness liest
  BEIDE und meldet Divergenz als Hinweis (nicht Defekt).
  Spec: CONFIRMED. Evidenz: MISSING.
- M7-S4 Isolation: W1 = `COURIER_STATE_FILE` zeigt in RUN-Verzeichnis (Prozess-Env
  belegt); W2 = Port-8080-frei-Protokoll VOR Start. Harness liefert BEIDES nicht
  (`--db`-Illusion). VERDIKT: CONFIRMED-GAP (M7-Paket Luecke 1).
- M7-S5 Null-Relay: W1+W2 = Akteur-Protokoll (wer claimte/lieferte/verifizierte?).
  Existiert NICHT (kein Actor-Logging). VERDIKT: CONFIRMED-GAP.
*M7-S6 entfernt (Follow-up): steht primaer in M2-S3 + M9/RUN1_EVIDENCE — hier nur noch dieser Zeiger.*

## OUTPUT
ROLE=M7
CONFIRMED=S1/S2/S3-Specs (Witness-Paare definiert); S3-Spiegel-Divergenz-Regel (neu, aus Q10-Lag); S4/S5-Gaps; S6-Bedingung
DISPROVEN="Log-Substrings sind Witnesses"; "Ein Zeuge (nur DB/nur Log) reicht"
MISSING_EVIDENCE=Alle RUN1-Evidenzen (5 Claims × 2 Witnesses) — nur RUN-Lane, nach Harness-Reparatur
OWNER_PACKET=RUN-Lane: Harness-Reparaturliste steht in `ops/ai/M1_M9/M7_RUN1_PROOF_CHAIN.md` M7.1-8 (hier nicht dupliziert); dazu Witness-Checkliste S1-S5 oben
CRITICAL_PATH=S4/S5-Gaps + M7.1-8 → M9 BEFORE_RUN1; S1-S3 → M9 RUN1_EVIDENCE
NEXT_OWNER=RUN-Harness-Owner (Reparatur); Mac-Operator (Ausfuehrung)
DO_NOT_REPEAT=Die 8 Harness-Luecken neu auflisten; SQLite-Checker diskutieren; RUN selbst starten
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M7
SURVIVING_CONFIRMED=M7-S1/S2 (Witness-Specs); M7-S3 (mit Historien-Caveat); M7-S4/S5 (Gaps)
REMOVED=M7-S6 (Duplikat → M2-S3/M9)
MINIMUM_NEXT_ACTION=Harness-Reparatur M7.1-8 (unveraendert); Mirror-Code-Refs bei Beruehrung frisch lesen (app.py mutiert)
MINIMUM_TEST_OR_EVIDENCE=RUN1-Evidenzen nach Reparatur (RUN-Lane)
NEXT_OWNER=RUN-Harness-Owner
STATUS=DONE_STATIC
