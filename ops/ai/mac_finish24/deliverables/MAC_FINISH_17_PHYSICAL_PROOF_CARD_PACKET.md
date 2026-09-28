# MAC-FINISH-17 — Physical Proof Card Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-17
- **Area**: PHYSICAL_PROOF_CARD_PACKET
- **Status**: COMPLETE

Defines the unforgeable Courier Physical Proof Card consolidating RUN_1, RUN_2, and candidate integrity evidence.

---

## 2. Proof Card Field Definitions

### Candidate-Independent Fields
- `ARCHITECTURE`: x86_64
- `OS_KERNEL`: Darwin 25.6.0
- `VERIFIER_HARNESS_VERSION`: v1.0-canonical
- `HASH_ALGORITHM`: SHA-256
- `ISOLATION_PORT`: 8081
- `MAX_HEAVY_JOBS`: 1

### Candidate-Sensitive Fields
- `FINAL_SHA`: `<FINAL_SHA>`
- `BASE_SHA`: `4c1e24ccc522042af826bc4c2b595daf85d097f9`
- `TARGETED_TESTS_RESULT`: 44/44 PASS
- `TWELVE_CASE_MATRIX_RESULT`: 12/12 PASS
- `RUN_1_ZERO_RELAY_VERDICT`: PASS
- `RUN_2_NO_REPLAY_VERDICT`: PASS
- `BLOCKCHAIN_LEDGER_HEAD`: `<LEDGER_HEAD_HASH>`
