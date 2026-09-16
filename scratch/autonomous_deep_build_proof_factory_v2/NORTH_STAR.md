# NORTH STAR: AUTONOMOUS DEEP BUILD & PROOF FACTORY V2

**MISSION ID**: `WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2`  
**STATUS**: `ACTIVE & AUTONOMOUS`  
**DATE**: `2026-09-09`  
**HOST**: `Windows (win32 x64 10.0.19045)`  

---

## 1. THE NORTH STAR ARCHITECTURE

The fundamental purpose of this factory is to advance the 2026 Courier system toward an autonomous agentic operating model:

```
HUMAN
  │ (States Objective & Invariants)
  ▼
[COURIER GOAL PLANE]
  │
  ├─► PLAN (Decompose into typed, bounded tasks)
  │
  ├─► ROUTE (Cost-aware worker dispatch & lease allocation)
  │
  ├─► EXECUTE (Sandboxed execution, zero-spend enforcement)
  │
  ├─► VERIFY (Independent cryptographic deliverable validation)
  │
  ├─► LEARN (Record findings & follow-up opportunities)
  │
  ├─► SELECT NEXT BEST WORK (Self-directed priority scoring)
  │
  └─► PROVE GOAL SATISFIED (Cryptographic satisfaction envelope)
```

---

## 2. THE MULTI-MODAL EVIDENCE STANDARD

Unlike synthetic test sweeps, a workstream or component cannot claim saturation without multi-modal evidence across the following 17 dimensions:

1. **Current-Source Inspection**: Verified against actual Courier production code paths.
2. **Explicit State Machine**: Formal states, legal transitions, forbidden edges.
3. **Shadow Implementation**: Complete, working component logic in `SHADOW_IMPLEMENTATION/`.
4. **Deterministic Unit Tests**: Baseline functional contracts.
5. **Property Tests**: Invariant holds across generative/arbitrary inputs.
6. **Metamorphic Tests**: Semantic input equivalencies produce invariant outcomes.
7. **Mutation Tests**: Injection of subtle logic errors; 100% critical mutant kill rate required.
8. **Fault Injection**: Mid-flight exceptions, timeouts, and resource errors.
9. **Crash / Restart Recovery**: Sudden process termination with durable reconciliation.
10. **State Migration**: Evolution of legacy schemas to modern envelopes without data loss.
11. **Atomic Rollback**: Strict LIFO compensation on partial failure.
12. **Replay Determinism**: Same event journal produces bit-for-bit identical derived state.
13. **Cross-Component Integration**: Inter-module contract validation.
14. **Long-Horizon Simulation**: Virtual soak runs (8h, 24h, 7d, 30d, 1y).
15. **Independent Oracles**: Dual-implementation differential verification.
16. **Minimized Counterexamples**: Concrete JSON payloads reproducing defects.
17. **Adversarial Review**: Uncompromising challenge against claiming saturation.

---

## 3. THE 40 MANDATORY EXPLORATION DOMAINS

1. Task Lifecycle
2. Goal Lifecycle
3. Worker Lease
4. Process Lease
5. No-Stacking / Resource Ownership
6. Crash Reconciliation
7. Execution Uncertainty
8. Dispatch Fence
9. Result Customs
10. Border Guard
11. Follow-Up Preservation
12. Human Gates
13. Zero-Spend Safety
14. Approval Binding
15. Migration
16. Rollback
17. Replay
18. Durable Audit
19. Resource Governor
20. Deadlock Detection
21. Starvation / Fairness
22. Goal Satisfaction
23. Notifications
24. Long-Run Autonomy
25. Legacy Compatibility
26. Multi-Fault Interactions
27. State Versioning
28. Idempotency
29. Duplicate Result Handling
30. Stale Message Handling
31. Partial Writes
32. Log Corruption
33. Clock / Time Assumptions
34. Process Identity
35. Queue Recovery
36. Dependency Propagation
37. Human Interruption Burden
38. Test Oracle Independence
39. Integration Order
40. Productization Contracts

---

## 4. INVARIANTS & SAFETY CONTRACT

- `AUTONOMOUS_SPEND_LIMIT_EUR = 0.00`
- `REAL_TRADES = 0`
- `REAL_FUNDS_TOUCHED = NO`
- `REAL_POSITIONS_CHANGED = 0`
- `REAL_WALLETS_CONNECTED = NO`
- `REAL_REVENUE_EUR = 0.00`
- `HOST`: Strictly Windows-local. NO MAC ACCESS.
- `PROTECTED REPOSITORIES`: Zero mutation of `happyhippovip/universuX`, RC3, or historical baseline logs.
- `PRODUCTION FENCE`: Zero modification outside `scratch/autonomous_deep_build_proof_factory_v2/`.
