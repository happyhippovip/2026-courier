# MUSE-HNI-11 checkpoint — CHANGED_ATTEMPT_DISPATCH_QA (read-only)

TASK_ID=MUSE-HNI-11 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T12:54Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_11_CHANGED_ATTEMPT_DISPATCH_QA.claim.json (atomic).
REUSED: app.py:325-333 (claim minting) + :138-140/:367 (binding) + adapter:133-139
(prior reads, not re-read).

SUBCASES (changed attempt/dispatch; 0 executions, ledger untouched):
S1 Stale attempt_id on result -> 400 mismatch (:138-140). SOUND.
S2 Stale dispatch_id on result -> 400 mismatch. SOUND.
S3 Claim resets result_id=None (:333); stale result_id cannot pre-bind a fresh
  attempt. SOUND.
S4 Resume mints fresh attempt_id + dispatch_id (:535-536); superseded attempt's
  results permanently unbindable. SOUND (R1 stored-result ACK exception cited).
S5 Adapter persisted-state dispatch mismatch -> ValueError, no POST (:136-137);
  POSTED short-circuit prevents double-post (:138-139). SOUND.
S6 run_attempt must be digit-string when present (:144-145). SOUND fail-closed.
S7 BOUNDARY: /verify re-checks result_id + artifacts only, not attempt/dispatch —
  correct layering (binding enforced once at intake :138-140; verify consumes the
  bound stored result). No gap.

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 0 false-greens).
NEXT=MUSE-HNI-12 (changed artifact/result).
