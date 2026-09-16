# PROGRESS UPDATE RULES V1

## Fundamental Invariants

### 1. Progress is Evidentiary, Not Chronological
The Symphony dashboard must **NEVER** advance progress simply because:
- Wall-clock time has passed.
- An autonomous agent ran for several hours or overnight.
- Many test runs or iterations were executed.
- A worker reported `DONE` or claimed saturation.
- Large LLM token quotas or compute cycles were consumed.

### 2. Acceptable Triggers for Progress Advancement
Progress may ONLY be updated when an authoritative, reproducible milestone is verified and accepted by Chief:
1. **New Production Capability Proven**: Canonical runtime entrypoint successfully executes an end-to-end lifecycle without harness orchestration.
2. **Critical Architectural Gap Closed**: An authoritative boundary (e.g. TaskPassport HMAC signing, BorderGuard hold, ResultCustoms independent disk verification) is wired and tested.
3. **Cross-Platform Verification Passed**: A platform-specific proof passes both on Windows and macOS with identical behavioral contracts.
4. **Real Human Gate Completed**: An explicit, authorized human decision is recorded and verified in the audit ledger.
5. **Real Commercial Revenue Observed**: Verified bank/payment ledger receipts confirm legitimate external customer transactions.

### 3. Strict Separation of Engineering vs Revenue
- Engineering completeness does **NOT** equal commercial revenue.
- `Revenue Proof` remains strictly **0% (€0.00)** until real customer funds are verified.
- Technical readiness (95%) must never be blurred with commercial proof (0%).

### 4. Ownership of Estimates
All subsystem and overall percentages are marked:
- `estimate_owner: CHIEF`
- `estimate_type: OPERATIONAL_ESTIMATE`
They reflect structured milestone estimations based on verified artifacts, not mathematical certainty.
