# CODEX INDEPENDENT REVIEW QUEUE — ARCHITECTURAL AUDIT ITEMS

The following core invariant designs and formal state models are queued for independent adversarial review by Codex:

1. **Multi-Factor Process Ownership Identification**
   - *Component*: `ProcessLeaseEngine`
   - *Review Focus*: Verifying that (PID + PPID + start_time + command_line + task_id) tuple prevents all OS PID recycling attack surfaces across all POSIX / Win32 kernels.

2. **Strict Fallback Invariant: DEFINITE_NO_EFFECT Precondition**
   - *Component*: `FallbackPolicyEngine`
   - *Review Focus*: Ensuring that no possible or uncertain execution state can ever be routed to a secondary worker without risking duplicate side-effects.

3. **Bounded Appeal Anti-Loop State Machine**
   - *Component*: `BorderAndCustomsEngine`
   - *Review Focus*: Verifying that `MAX_APPEALS = 3` with monotonic transition to `REJECTED_FINAL` provably terminates all potential worker/supervisor ping-pong cycles.

4. **42-Field Courier Task Passport HMAC Verification**
   - *Component*: `BorderAndCustomsEngine`
   - *Review Focus*: Cryptographic review of the canonical payload hash signing scheme, nonce uniqueness, and clock skew tolerance window.
