# MAC-FINISH-11 — Verify Reconcile Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-11
- **Area**: VERIFY_RECONCILE_PACKET
- **Status**: COMPLETE

Defines the verifier authority contract, reconciliation state machine, and ledger entry creation.

---

## 2. Verifier Authority
- The verifier operates with isolated authority and dedicated credentials (`COURIER_VERIFIER_API_KEY`).
- The verifier independently inspects artifacts, compares hashes, and signs verification attestations.

---

## 3. State Machine Transitions
`SUBMITTED` -> `VERIFYING` -> `RECONCILED` (or `REJECTED`)
- When marked `RECONCILED`:
  - An entry is appended to `ops/ai/wall_ledger/ledger.jsonl`.
  - A cryptographically linked block is inserted into `ops/ai/wall_ledger/ledger.db`.
  - Dependent downstream tasks are instantly notified.
