# WALL 05 — STALE_IDENTITY_ATTACKS (READ_ONLY)

WALL_ID=05 (first-free; 02+03 belegt)
ROLE=14 STALE_IDENTITY_ATTACKS
DATE=2026-09-28
HEAD=34b0a4264bf763bc2a78f761ffba36e47706b2cf (fix-cb1-new, loser Ref; == REVIEW_SHA)

## Bezugsrahmen (akzeptiert, kein Re-Review)
REVIEW_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
SONNET_VERDICT=BLOCKED (verify_artifacts unhashable-dict; Fix: SOLE_WINDOWS_WRITER)
PHASE_RECORD: OLD_e5751783 -> NEW_34b0a42 (Ref-Wanderung diese Session).
MATERIAL_DELTA=Verifier-Rewrite (WALL_03-Delta bestaetigt); app.py/contract/artifact_store
an den hier zitierten Stellen wortgleich zu e575178-Reads (diese Session re-verifiziert).
EVIDENCE_INVALIDATED=e575178-Zeilennummern (Inhalt re-geprueft, gueltig).
EVIDENCE_REUSABLE=MUSE9_M4 (Replay-Mechanik), MUSE9_M5 (Heartbeat/Reclaim-Mechanik) —
diese Lane prueft ANGRIFFE, nicht Mechanik (kein Duplikat).
VERDICT_TRANSFER=NONE (kein Ersatz-Gate-Review).

## Subcases (vollstaendige Lane, 6/6)

CASE=14-1_STALE_WORKER_RETURNS_AFTER_QUARANTINE
SHA=34b0a42
RUN_ID=NONE_STATIC
SOURCE_TRUTH=reclaim loescht worker.current_task, NICHT task.worker_id
(app.py:441-448); task steht HUMAN_REQUIRED.
ACTUAL_EVIDENCE=Kein Lauf beobachtet (kein Server in diesem Fenster).
REUSED_EVIDENCE=M5-S2 (Quarantaene-Mechanik), M5-S5 (lebender Stale-Fall task-replace-001).
VERDICT=ATTACK_FAILS: alter Worker postet -> :372 worker match -> :373
status!=DISPATCHED -> 409. Nach Resume+Neuvergabe: worker mismatch -> 400 (:413).
FALSE_GREEN_RISK=LOW (Antwortcodes staten Maschine ab, kein PASS-Pfad).
MISSING=Laufzeit-Beobachtung des 409/400 (RUN-Lane).
SOURCE_FIX_REQUIRED=NO
PHYSICAL_ACTION_REQUIRED=NO
OWNER=NONE (Design haelt)

CASE=14-2_WRONG_WORKER_POSTS_FOREIGN_DISPATCH
SHA=34b0a42
RUN_ID=NONE_STATIC
SOURCE_TRUTH=:372 task.worker_id==worker_id sonst 400 (:413). Key-Besitz
vorausgesetzt (geteilte Worker-Keys: Threat-Modell ausserhalb Scope).
ACTUAL_EVIDENCE=Kein Lauf beobachtet.
REUSED_EVIDENCE=M4-S3 (Konflikt-Codes).
VERDICT=ATTACK_FAILS (400, kein Partial-Write: Save nur im Match-Zweig :410).
FALSE_GREEN_RISK=LOW.
MISSING=Keine (Code-Pfad total).
SOURCE_FIX_REQUIRED=NO
PHYSICAL_ACTION_REQUIRED=NO
OWNER=NONE

CASE=14-3_STALE_ATTEMPT_AFTER_RETRY
SHA=34b0a42
RUN_ID=NONE_STATIC
SOURCE_TRUTH=validate bindet goal/task/attempt/dispatch/worker exakt
(contract.py:138-140); Retry->frische attempt/dispatch beim naechsten Claim
(app.py:327-331,534-540). Alte Results binden nie wieder.
ACTUAL_EVIDENCE=Kein Lauf beobachtet.
REUSED_EVIDENCE=M4 DISPROVEN "Resume-Replay alter Results".
VERDICT=ATTACK_FAILS (400 attempt/dispatch mismatch).
FALSE_GREEN_RISK=LOW.
MISSING=Keine (Code-Pfad total).
SOURCE_FIX_REQUIRED=NO
PHYSICAL_ACTION_REQUIRED=NO
OWNER=NONE

CASE=14-4_VERIFIER_SELF_CERT_AND_SUBSTITUTION
SHA=34b0a42
RUN_ID=NONE_STATIC
SOURCE_TRUTH=verifier_id!=worker_id + Pflicht (:485), result_id-Gleichheit
(:488), Artifact-Gleichheit (:490, jetzt reihenfolge-sensitiv), separater
Verifier-Key (:33-44). RECONCILED-Dup nur bei gleichem result_id (:476-480).
ACTUAL_EVIDENCE=Kein Lauf beobachtet.
REUSED_EVIDENCE=M4-S2/S3 (Verify-Codes, Refs hier aktualisiert).
VERDICT=ATTACK_FAILS (400/409 je Variante). SONNET-BLOCKER UNBERUEHRT:
Blocker liegt VOR diesen Checks (set() :62-63 wirft Exception statt FAIL).
FALSE_GREEN_RISK=LOW (fuer Identitaet; Effekt-Seite -> Sonnet-Fix).
MISSING=Laufzeit-Beobachtung (RUN-Lane).
SOURCE_FIX_REQUIRED=NO (fuer 14-4; Sonnet-Fix separat beim Writer)
PHYSICAL_ACTION_REQUIRED=NO
OWNER=SOLE_WINDOWS_WRITER (nur Sonnet-Blocker, bereits routed)

CASE=14-5_ARTIFACT_CROSS_DISPATCH_REBINDING
SHA=34b0a42
RUN_ID=NONE_STATIC
SOURCE_TRUTH=Upload nur an DISPATCHED (:184 artifact_store Blueprint),
Binding-Felder muessen matchen (:186-188), Name muss erwartet sein
(:189-191); check_reference vergleicht alle 5 Binding-Felder + name/sha/size
(artifact_store.py:133-144); Verifier-Seite analog (:147-159). Blob-Sharing
ist content-adressiert (by design), Records sind dispatch-gebunden.
ACTUAL_EVIDENCE=Kein Lauf beobachtet.
REUSED_EVIDENCE=MUSE9_M4 (Artifact-Identitaet), M7-Kette (Hash-Behauptungen).
VERDICT=ATTACK_FAILS (400/409/FAIL je Schicht, 3 Schichten tief).
FALSE_GREEN_RISK=LOW.
MISSING=Keine (Code-Pfade total).
SOURCE_FIX_REQUIRED=NO
PHYSICAL_ACTION_REQUIRED=NO
OWNER=NONE

CASE=14-6_HEARTBEAT_RESURRECTION_AFTER_STALE
SHA=34b0a42
RUN_ID=NONE_STATIC
SOURCE_TRUTH=Reclaim: current_task=None + available=False (:446-448).
Heartbeat danach: available=True wenn kein current_task + nicht unregistered
(:250-254). Worker darf NEUE Arbeit claimen; alte Task bleibt
HUMAN_REQUIRED/BLOCKED (14-1).
ACTUAL_EVIDENCE=Kein Lauf beobachtet.
REUSED_EVIDENCE=M5-S1/S2 (Zahlen + Quarantaene).
VERDICT=NO_HOLE_BY_DESIGN (Liveness, keine Identitaets-Verletzung).
FALSE_GREEN_RISK=LOW.
MISSING=Keine.
SOURCE_FIX_REQUIRED=NO
PHYSICAL_ACTION_REQUIRED=NO
OWNER=NONE

## Neben-Notiz (kein Finding)
contract.py:154-156 enthaelt ein doppeltes Set-Literal (harmlos redundant).
Nicht file-wuerdig; hier notiert gegen Busywork.

## Deltas zu e575178-Reads (bestaetigt, keine Befunde)
- Dup-Compare :367 jetzt 6 Felder ohne goal/task + reihenfolge-sensitiv
  (war sort-insensitiv). Kein Angriffspfad (dispatch_id uuid-eindeutig).
- Verify-Artifact-Compare :490 jetzt reihenfolge-sensitiv. Strikter, kein Loch.

## Pool (bounded check)
POOL_SCRIPT=weiter MISSING (eigener Glob: 0 Treffer)
SHELL=DOWN -> Claim/Complete/Block nicht ausfuehbar
POOL_STATUS=UNAVAILABLE (identisch WALL_02/03; kein NO_TASK behauptet)

## FINAL (WALL_05)
SLOT_ID=05
LANE=14_STALE_IDENTITY_ATTACKS
CURRENT_PHASE=BLOCKED_GATE_SONNET_34b0a42; Checkout==REVIEW_SHA (neu)
CURRENT_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
RUN_ID=NONE_STATIC
SUBCASES=14-1,14-2,14-3,14-4,14-5,14-6
PROVEN=6/6 Angriff schlaegt fehl (statisch, Code-Pfade total)
FAIL=0
UNKNOWN=0 Befunde; Laufzeit-Beobachtungen offen (RUN-Lane, nicht hier)
WRITER_PACKET=NONE (kein neuer Fix-Bedarf; Sonnet-Blocker bereits bei Writer)
PHYSICAL_PACKET=NONE
LANE_COMPLETE=YES
NEXT_TRIGGER=RUN1/RUN2-Evidenz (Angriffsfaelle live beobachten) ODER neue ROLE/Claim bei Pool-Verfuegbarkeit
