# Courier Safety Invariants

This document establishes the permanent safety invariants for the Courier orchestration architecture. These rules are non-negotiable and must not be silently regressed.

1. **Durable execution lease bound to task/attempt/dispatch/worker:** A task is leased to a worker using a uniquely generated lease_id.
2. **Reject forged/manual/wrong/expired SUCCESS:** Task execution status can only advance using a valid lease_id and correct role authorization. Fake or dummy success payloads must be rejected.
3. **Verifier-only RECONCILED/DONE:** The final RECONCILED or DONE state can only be achieved via the independent verifier. Workers can only report RESULT_RECEIVED.
4. **HUMAN_REQUIRED cannot be cleared autonomously:** Only manual human intervention can advance a task out of the HUMAN_REQUIRED state.
5. **Windows durable power-loss recovery + preserved execution identity:** The worker maintains state across reboots using atomic markers (ffect_marker.json).
6. **Independent heartbeat during long execution:** Workers execute an independent background heartbeat thread to prevent being erroneously marked as stale during long-running tasks.
7. **VERIFY_AFTER_CRASH/QUARANTINE instead of blind duplicate retry:** Workers finding a stale effect marker on boot report AMBIGUOUS_CRASH, preventing blind retries.
8. **Separate worker/verifier authority:** Distinct credentials for each role (COURIER_WIN_API_KEY, COURIER_MAC_API_KEY, COURIER_VERIFIER_API_KEY).
9. **Secure credentials / no secret logging:** Logs and state payloads must never include plaintext secrets or API keys.
10. **Compact one-line Courier health/status command:** scripts/courier_status.py provides exact COURIER OK | SERVER OK... formatting.
11. **Deterministic regression tests:** Verification of all safety constraints.
12. **Remove recovery-only fake/manual submission scripts:** No backdoor submissions allowed.
