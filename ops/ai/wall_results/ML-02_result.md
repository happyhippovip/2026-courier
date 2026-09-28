# Result for ML-02 — Replay negative-case QA

TASK_ID=ML-02
STATUS=PROVEN
RESULTS_REUSED=GLEDGER-111..120, G201..G210, FAMILY_23_REPLAY_PROOF_SYNTHESIS.md, server/app.py:382-414, tests/test_p3_server_idempotency.py
FALSE_GREEN_PATH=NONE_DETECTED
MISSING_EVIDENCE=NONE
FALSIFYING_CONDITION=Any replay with modified worker_id, status, attempt_id, dispatch_id, or artifact hash receiving an ACK_DUPLICATE (HTTP 200) instead of HTTP 409 Conflict.
NEXT_EXACT_ACTION=PROCEED_TO_ML_03
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-ml-02-replay-qa-proven-20260928

## Adversarial QA Analysis
1. 5-Tuple Idempotency Check: `server/app.py` inspects stored vs incoming `(dispatch_id, result_id, status, worker_id, attempt_id, artifacts)`.
2. Negative Case Evaluation:
   - Changed worker_id -> HTTP 409 Conflict (proven).
   - Changed status -> HTTP 409 Conflict (proven).
   - Changed attempt_id -> HTTP 409 Conflict (proven).
   - Changed artifact hashes -> HTTP 409 Conflict (proven).
3. Post-Restart Replay: `server/state/central_state.json` reload preserves identical duplicate detection across daemon restarts.
4. Verdict: No false duplicate ACK path exists. Idempotency fails closed.
