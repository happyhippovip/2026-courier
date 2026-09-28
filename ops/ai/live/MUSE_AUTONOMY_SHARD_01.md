# SHARD 01 — Returned-Result-Policy (auto persist/classify/reconcile/READY?)

SHARD=01
STATUS=COMPLETE (5 Subcases, 0 Executions, 0 Edits, Ledger frozen)
POLICY=ops/ai/RETURNED_RESULT_POLICY.md (gelesen)

SUBCASES_DONE=5 (Source > Prosa; Refs auf HEAD e11749b6-Linie):
1. Persist+Classify: POST /tasks/result validiert→RESULT_RECEIVED;
   FAILED→QUEUED-Auto-Retry, erst 3. Versuch→FAILED_TERMINAL+BLOCKED
   (server/app.py:376-404). Kein Human-Call im Pfad. AUTOMATISCH.
2. Verify→Reconcile→Advance: PASS→RECONCILED + current_step_index+1
   (Z. 503-507); nächster Claim liefert Nachfolger (Z. 277-350).
   AUTOMATISCH ohne Human-Prompt.
3. Duplikat/spät: identisch→ACK_DUPLICATE, abweichend→409 (Z. 364-370).
   Kein Doppel-Effekt, kein Human. AUTOMATISCH.
4. Ambig/stale: reclaim→HUMAN_REQUIRED + Goal BLOCKED (Z. 433-449);
   spätes Result→409 (Z. 373-374); Resume nur retry, force_success=400
   (Z. 546-549). Kette STOPPT für Human — per Policy §8
   (WAITING/BLOCKED-Wall) KONFORM, fail-closed by design.
5. Exhaustion: nichts READY → {"task": None} 200 (Z. 349-350), kein
   Error, kein Busy-Loop-Anreiz. Policy-NO-Branch KONFORM.

CONFIRMED_SOURCE_DEFECTS=0 (neu). REUSE: Register-Divergenz-Rewind
(AUCH RESULT_RECEIVED→HUMAN_REQUIRED, Z. 195-208) aus
MUSE_MAC_STATE_TRUTH.md — Owner-Aktion, hier nicht erneut geprüft.
EVIDENCE_GAPS=0 (neu). Policy-Schritte 4-7 sind Agenten-Disziplin +
  Claim-Matching/Cost-Routing (Z. 273-326, partiell im Code) — kein Defect.
DISPROVEN="Human als normaler Scheduler nötig" (Happy Path läuft
  result→verify→reconcile→READY→dispatch ohne Human-Call).
FIX_PACKETS=0.
NEXT_OWNER=— (kein Owner nötig)
DO_NOT_REPEAT_FINGERPRINT=muse-shard01-returned-result-e11749b6
