# MUSE-HNI-10 checkpoint — CHANGED_WORKER_REJECTION_QA (read-only)

TASK_ID=MUSE-HNI-10 / OWNER=MUSE_C2_LAPIS_DUBHE / HOST=MAC / 2026-09-28T12:46Z
GATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated).
CLAIM=ops/ai/wall_claims/MUSE_HNI_10_CHANGED_WORKER_REJECTION_QA.claim.json (atomic).
REUSED: result-binding sections (HNI-08/09 + prior reads); cross-proc lock residual
(MMAC-057, cited only); claim-file-liveness limit (known, cited only).

SUBCASES (changed-worker rejection; 0 executions, ledger untouched):
S1 Wrong worker_id on result -> 400 mismatch (contract:138-140 via app.py:376-381).
  SOUND.
S2 BOUNDARY: require_auth checks ONE shared Bearer key (app.py:21-31); worker_id
  is self-asserted in body. Enforced binding = result<->task, NOT caller<->worker.
  Trust root = key-holder set. Fail-closed on mismatch; authority note, no finding.
S3 Unknown worker claim -> 404 (:272-273); busy worker -> task None (:277-279).
  SOUND.
S4 Only QUEUED claimable (:286); DISPATCHED invisible to second claimant.
  SOUND single-process (serialize_state_mutation; cross-proc residual known/cited).
S5 Verifier==worker -> 400 (:485); VERIFIER_API_KEY must differ from API_KEY or
  the verify plane 503s (config-level separation). SOUND.
S6 Post-resume late result from old worker: worker_id=None (:539-540) ->
  mismatch 400. SOUND.
S7 Heartbeat unknown -> 404; unregister sticky (:237-242). Liveness != authority;
  claim files prove no liveness (known, cited only).

VERDICT=COMPLETE (candidate-independent; 0 contradictions, 1 documented boundary).
NEXT=MUSE-HNI-11 (changed attempt/dispatch).
