# L20 LEDGER FINAL GATE PACKET

## Objective
Provide the exact closure order and evidence requirements to move the Ledger from its current 9/10 readiness state (gaps mapped, red tests authored) to 10/10 production readiness (all tests green, all contracts enforced).

## Current State (9/10)
Through L01-L19, we have mapped every architectural boundary. We proved that the Journal replay mechanism and the state machine's core state-transition fencing are fully mathematically secure (L14-L18). However, four distinct semantic gaps exist in the peripheral logic that require production code mutations to turn the authored red tests green.

## 9/10 -> 10/10 Closure Order

The final transition requires executing four focused pull requests in the following order to minimize regression risk:

### Phase 1: Controller State Integrity (Retry Uncertainty)
- **Target**: `courier_core/state_machine.py`
- **Action**: Implement the `L02` contract. Update `decide_after_failure()` and `_transition()` to aggressively reject `retryable=True` hints from non-idempotent adapters. Any non-idempotent failure MUST transition the task to `TaskStatus.BLOCKED`.
- **Evidence for Green**: The `tests/core/test_l03_retry_matrix.py` red tests must pass.

### Phase 2: Outbox & Network Hardening (Unknown 2xx)
- **Target**: Worker HTTP Transport / Delivery loops (`courier_worker/` or equivalent).
- **Action**: Implement the `L12` contract. The delivery webhook must explicitly parse the `JSON` response for `{"status": "ACK_ACCEPTED" | "ACK_DUPLICATE" | "ACK_REJECTED"}`. A generic `200 OK` must be treated as a delivery failure, retaining the payload in the outbox (`L13`).
- **Evidence for Green**: The `tests/test_l12_unknown_2xx_hardening.py` red tests must pass.

### Phase 3: Provider Conformance (Effect Key Gate)
- **Target**: Worker Adapter execution boundary (`courier_worker/adapters.py`).
- **Action**: Implement the `L09` contract. Adapters marked as `idempotent` must statically require and use `effect_key`. If the key is stripped, dropped, or mismatched, the task must fail safely before external execution.
- **Evidence for Green**: The `tests/test_l10_effect_key_negative.py` synthetic negative tests must pass.

### Phase 4: Time/Lease Alignment (Canonical Timeout)
- **Target**: Worker loop pacing (`courier_worker/`).
- **Action**: Implement the `L07` L2/L3 alignment plan. Windows and macOS workers must uniformly obey the controller's absolute TTL expiration. Local wall-clock variations must not allow a worker to execute a task after the controller has marked the lease expired.
- **Evidence for Green**: Cross-worker endurance tests proving zero write-after-timeout violations under load.

## Final Acceptance
Once Phases 1-4 are merged, the `L19_LEDGER_ACCEPTANCE_REGISTRY` serves as the CI/CD pipeline baseline. When all mapped L01-L18 tests pass on the main branch, the Ledger achieves **10/10 Production Readiness**. No further structural architectural changes are permitted without a formal revalidation cycle (CORE_FREEZE).
