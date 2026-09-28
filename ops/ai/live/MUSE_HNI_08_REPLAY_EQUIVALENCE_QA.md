# MUSE-HNI-08 checkpoint — REPLAY_EQUIVALENCE_QA (read-only)

TASK_ID=MUSE-HNI-08 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T12:30Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_08_REPLAY_EQUIVALENCE_QA.claim.json (atomic).
REUSED (not re-proven): F1/F2 ACK-narrowness + R1 resume-no-clear (cited only);
server/app.py:352-545 (prior read); adapter run() prior-state (:133-139, this run).

SUBCASES (duplicate equivalence, source > prose; 0 executions, ledger untouched):
S1 6-tuple identical resend -> ACK_DUPLICATE (app.py:367-368: dispatch/result/
  status/worker/attempt/artifacts). SOUND — attempt+dispatch in key.
S2 Ordering: stored-match check (:367) BEFORE terminal-state 409 (:369). Same
  result on RESULT_RECEIVED task ACKs, never conflicts. SOUND.
S3 Changed payload, same dispatch, processed task -> 409 (:369-370); on DISPATCHED
  task -> validate_durable_result mismatch -> 400. No silent overwrite. SOUND.
S4 Verify resend same result_id on RECONCILED -> ACK_DUPLICATE (:476-479);
  different result_id -> 409 (:480). SOUND.
S5 Resume-retry mints fresh attempt/dispatch (:535-536); superseded result can't
  rebind (400). R1 exception (stored result not cleared -> identical replay ACKs)
  = known, cited only.
S6 Adapter crash POST-vs-state-write: prior POSTED -> return 0, no re-POST
  (adapter:138-139); identical re-POST -> server ACK_DUPLICATE (S1). SOUND.
S7 Quarantined (HUMAN_REQUIRED) task result POST -> 409 (:373-374, not DISPATCHED).
  No replay out of quarantine except resume->QUEUED->fresh identity. SOUND.

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 0 false-greens).
NEXT=MUSE-HNI-09 (changed-status rejection).
