# L05: TIMEOUT_PATH_MAP

## The Problem
Timeout and lease semantics diverge drastically depending on which boundary (Controller/L2 vs Worker/L3) observes the deadline first. A timeout is conceptually a "lease lost" situation, but the current routing changes the event type and downstream idempotency protection.

## Identified Paths

### 1. Controller Watchdog Expiration (L2)
* **Source:** `courier_core/controller.py` watchdog loop (`_sweep_leases`).
* **Trigger:** Wall-clock time without a heartbeat exceeds the deadline (based on `lease_ttl_s`).
* **Emits Event:** `LEASE_EXPIRED` (reason="ttl" or "restart_grace").
* **State Machine Effect:** `status=RETRY_PENDING`, `failure_kind="lease_lost"`.
* **Decision Evaluation:** `decide_after_failure` checks idempotency. If `started=True` and `effect_class=non_idempotent`, it safely returns `Decision.BLOCK`.

### 2. Worker Lease Bound (L3)
* **Source:** `courier_worker/host.py` (`lease_at` calculation).
* **Trigger:** Host process runtime exceeds `spec.lease_ttl_s`.
* **Emits Event:** `RESULT_REJECTED` (via `POST /result`), with `reason="worker outcome: lease-lost"` and `retryable=True`.
* **State Machine Effect:** `status=RETRY_PENDING`, `failure_kind="rejected"`.
* **Decision Evaluation:** Prior to L02's contract, `decide_after_failure` sees `retryable=True` and incorrectly returns `Decision.RETRY`, violating the uncertainty contract.

### 3. Worker Timeout Bound (L3)
* **Source:** `courier_worker/host.py` (`timeout_at` calculation).
* **Trigger:** Host process runtime exceeds `spec.timeout_s` (where `timeout_s` <= `lease_ttl_s`).
* **Emits Event:** `RESULT_REJECTED` (via `POST /result`), with `reason="worker outcome: timeout"` and `retryable=True`.
* **State Machine Effect:** `status=RETRY_PENDING`, `failure_kind="rejected"`.
* **Decision Evaluation:** Treated identically to Path 2. It incorrectly results in `Decision.RETRY` for non-idempotent tasks.

## Semantic Divergence
The core semantic flaw is that L3 (the worker) treats timeouts and lease losses as "failures" (`RESULT_REJECTED`), while L2 (the controller) treats lease losses as an infrastructural meta-event (`LEASE_EXPIRED`). Because `RESULT_REJECTED` bypasses the `failure_kind="lease_lost"` branch in the state machine, L3 timeouts evade the idempotency protections built into the L2 lease expire path.
