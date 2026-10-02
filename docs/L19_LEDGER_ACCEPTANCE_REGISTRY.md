# L19 LEDGER ACCEPTANCE REGISTRY

## Objective
Map the exact checks, tests, and contracts required to declare the Ledger "green" (10/10 production readiness). This registry serves as the canonical criteria for the final QA gate.

## Criteria and Evidence Mapping

### 1. Non-Idempotent Retry Trust & Uncertainty (L01-L04)
- **Criterion**: The Ledger must never blindly trust a worker's `retryable=True` claim for non-idempotent tasks that fail, since the actual execution effect is uncertain. Such tasks must transition to `BLOCKED`.
- **Contract**: Defined in `docs/L02_RETRY_UNCERTAINTY_CONTRACT.md`.
- **Evidence/Checks Required for Green**:
  - `tests/core/test_l01_retry_trust.py`: Proves baseline behavior.
  - `tests/core/test_l03_retry_matrix.py`: Red test matrix enforcing strict block-on-uncertainty.
  - `tests/core/test_l04_retry_replay.py`: Ensures replay logic preserves uncertain state.

### 2. Timeout Semantics & Alignment (L05-L07)
- **Criterion**: Timeout rules must not diverge across worker lines (Windows vs. Mac). The controller's TTL must unconditionally dictate lease expiration, preventing execution-after-timeout.
- **Contract**: Unified semantics chosen in `docs/L06_CANONICAL_TIMEOUT_LAW.md`.
- **Evidence/Checks Required for Green**:
  - `docs/L05_TIMEOUT_PATH_MAP.md`: Identifies all path divergences.
  - `docs/L07_TIMEOUT_FIX_PLAN.md`: Actionable L2/L3 alignment packet for enforcing the single TTL law.

### 3. Provider Idempotency & Effect Keys (L08-L10)
- **Criterion**: Idempotency enforcement requires the `effect_key` to strictly govern adapter behavior. Provider execution must be gated upon valid key presence.
- **Contract**: Defined in `docs/L09_EFFECT_KEY_CONFORMANCE_GATE.md`.
- **Evidence/Checks Required for Green**:
  - `tests/test_l08_effect_key_dataflow.py`: Traces dataflow to boundary.
  - `tests/test_l09_effect_key_conformance.py`: Validates conformance logic.
  - `tests/test_l10_effect_key_negative.py`: Ensures missing/mismatched keys fail securely.

### 4. Result Acknowledgement & Outbox Durability (L11-L13)
- **Criterion**: Result delivery must not treat arbitrary or empty HTTP 2xx responses as canonical acceptance. The outbox must durably retain the payload against transport ambiguity.
- **Contract**: Strict parsing semantics defined in `docs/L12_UNKNOWN_2XX_HARDENING.md`.
- **Evidence/Checks Required for Green**:
  - `tests/test_l11_result_ack_enumeration.py`: Validates exact HTTP response parsing.
  - `tests/test_l12_unknown_2xx_hardening.py`: Red test failing on generic 200 OK.
  - `tests/test_l13_outbox_durability.py`: Proves payload survives transport faults.

### 5. Replay, Stale Workers, & Verification (L14-L18)
- **Criterion**: The journal must structurally refuse replays, write-after-transfer (stale workers) must be fenced, verifier authority must remain bounded by the controller, and `RESULT_READY` must strictly pass verification before canonical acceptance.
- **Evidence/Checks Required for Green**:
  - `tests/controller/test_l14_duplicate_result_replay.py`: Fences conflicting/duplicate replays.
  - `tests/controller/test_l15_late_result_fencing.py`: Fences stale `dispatch_id` results.
  - `tests/controller/test_l16_result_ready_acceptance.py`: Traces secure acceptance pipeline.
  - `tests/controller/test_l17_verifier_authority.py`: Proves verifier cannot spoof identity.
  - `tests/controller/test_l18_journal_replay_closure.py`: Proves strict state transitions and deduplication.

## Conclusion
The Ledger achieves "green" readiness when all deterministic red tests in the above registry pass continuously and the `L07` timeout fix plan is fully integrated into the worker daemon logic. This registry forms the final ledger validation packet.
