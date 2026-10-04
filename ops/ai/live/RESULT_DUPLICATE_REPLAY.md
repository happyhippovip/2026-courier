# Duplicate and Replay Semantics for /tasks/result

Testing completed using `tests/test_duplicates.py`.

A) **/tasks/result Duplicate-Guard-Reihenfolge**: Verified. The duplicate check correctly occurs before the terminal state 409 check and before the worker ownership check. This ensures that an exactly matched replay is always ACKed, even if the task has moved to a terminal state or a new attempt is currently dispatched.

B) **ACK_DUPLICATE erreichbar**: Verified. Sending the exact identical `identity` block (including matching artifacts) successfully triggers `{"status": "ACK_DUPLICATE"}`, code 200.

C) **Identischer Replay**: Verified. An identical replay of a result for an already-processed task hits the `ACK_DUPLICATE` path safely without returning an error.

D) **Changed Worker**: Verified. Returns `409 Conflicting result for already processed task` if the task is in `RESULT_RECEIVED`.

E) **Changed Attempt**: Verified. Returns `409 Conflicting result for already processed task`.

F) **Changed Dispatch**: Verified. Returns `409 Conflicting result for already processed task`.

G) **Changed Artifact Result**: Verified. Returns `409 Conflicting result for already processed task`.

**Conclusion**: The implementation in `server/app.py` for Duplicate Guards is flawless and strictly conforms to the expected behavior. No fixes were needed, but a robust regression test was added to `tests/test_duplicates.py`.
