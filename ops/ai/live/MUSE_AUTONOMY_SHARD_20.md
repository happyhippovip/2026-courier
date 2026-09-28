# SHARD 20 — Restart No-Replay (FAILED-Requeue-Fenster)

SHARD=20
STATUS=COMPLETE (5 Subcases, 0 Executions, 0 Edits, Ledger frozen)
SOURCE=server/app.py (task_result 352-413, claim 260-350, reclaim 416-454,
resume 518-550); REUSE MMAC-015/R1 (retry cleared nichts), MAC06 §6
(checkpoint-Quarantäne), MUSE_HNI_13-Lane (peer, nicht betreten).

SUBCASES_DONE=5 (alle code-gelesen, kein Re-Run):
1. Stale-Result im QUEUED-Fenster: FAILED-Result → QUEUED + worker=None
   (Z. 388-390, IDs NICHT refresht); Resubmit alter Payload → 409
   "not awaiting a result" (Z. 373-374), kein Bind. KEIN Replay.
2. Stale task["result"] bleibt nach retry bestehen (R1, REUSE) — kein
   Consumer liest result ohne Status-Gate: verify verlangt
   RESULT_RECEIVED (Z. 481), pending_verification filtert ebenso
   (Z. 462). Benign, kein Pfad zum Fehlverhalten gefunden.
3. Post-Retry-Claim mint frische attempt/dispatch (Z. 329-331); alter
   Worker-Payload scheitert an Identitätsbindung 400 (contract:138-140).
   KEIN Replay fremder Attempts.
4. Reclaim vs FAILED-Requeue: reclaim fasst nur DISPATCHED-Steps an
   (Z. 436); QUEUED-nach-FAILED bleibt claimbar — automatische
   Fortsetzung ohne Human-Park. Liveness erhalten, kein Replay.
5. Doppel-Claim: zweiter Claim sieht DISPATCHED≠QUEUED → {"task": None}
   (Z. 282). Gleicher Step nie zweimal aktiv. KEIN Doppel-Dispatch.

CONFIRMED_SOURCE_DEFECTS=0. EVIDENCE_GAPS=0.
DISPROVEN="Requeue-Fenster erlaubt Replay/Fehlbindung" (409-Gate +
  frische IDs schließen es).
FIX_PACKETS=0. NEXT_OWNER=—.
DO_NOT_REPEAT_FINGERPRINT=muse-shard20-noreplay-e11749b6
