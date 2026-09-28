# MAC-FINISH-06 — Event Correlation Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-06
- **Area**: EVENT_CORRELATION_PACKET
- **Status**: COMPLETE

Defines end-to-end correlation IDs, structured telemetry logging, and timestamp ordering across components.

---

## 2. Correlation ID Scheme
- Format: `CORR-{SESSION_ID}-{TASK_ID}-{EPOCH}`
- Example: `CORR-RUN1-TASK-A-1727484600`
- Propagation: Embedded in HTTP header `X-Courier-Correlation-ID`, recorded in coordinator logs, worker logs, and verifier payloads.

---

## 3. Causality & Event Sequence
An uncorrupted execution flow must show strict monotonic timestamps across 6 discrete events:
1. `TASK_DISPATCHED` (Coordinator)
2. `TASK_CLAIMED` (Worker)
3. `ARTIFACT_STORED` (Coordinator)
4. `RESULT_SUBMITTED` (Worker)
5. `VERIFICATION_COMPLETED` (Verifier)
6. `TASK_RECONCILED` (Coordinator)
