# INTEGRATION DEPENDENCY GRAPH & STAGING ORDER ANALYSIS

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Scope**: Rigorous evaluation of the dependency topology between A01, L01, G01, and B01.

---

## 1. DEPENDENCY TOPOLOGY MATRIX

```text
       [ A01: Execution-Uncertainty Fence ]
                     ▲
                     │ (G01 requires A01: Unsettled financial effects must not redispatch)
                     │
       [ G01: Deferred Financial Liability Gate ]
                     ▲
                     │ (Co-located: Mutative tasks must declare scopes & financial status)
                     │
       [ L01: Hierarchical Resource Lock Engine ]
                     ▲
                     │ (B01 provides process identity for safe L01 lease reclamation)
                     │
       [ B01: Multi-Factor Process Identity ] (Post-Freeze Mac Native Proof)
```

### Direct Inter-Component Dependencies

| Downstream Component | Depends On | Nature of Dependency | Severity if Integrated Out of Order |
|---|---|---|---|
| **G01** (Financial Liability Gate) | **A01** (Uncertainty Fence) | **HARD DEPENDENCY**. If a financial operation (e.g. checkout, payment authorization) crashes or enters an uncertain execution state, it MUST NOT be automatically retried. If G01 is integrated *before* A01, a gated financial task could be retried under uncertainty, causing duplicate billing. | **P0 (Financial Duplication)** |
| **L01** (Resource Locks) | **A01** (Uncertainty Fence) | **SOFT DEPENDENCY**. If an uncertain task continues to hold locks or is redispatched without lease cleanup, duplicate writers collide. A01 guarantees uncertain tasks hold until reconciled. | **P1 (Resource Lock Leak)** |
| **L01** (Resource Locks) | **B01** (Process Identity) | **CROSS-RELIANCE**. Releasing an L01 write lease upon worker exit requires knowing whether the process actually terminated or if its PID was recycled. B01 ensures leases are not released prematurely or held by zombies. | **P1 (Stale Lock / Premature Release)** |
| **G01** (Financial Liability Gate) | **L01** (Resource Locks) | **ORTHOGONAL**. Financial liability is control-plane/external, whereas L01 is resource-plane/internal. However, financial ledger writes require L01 `file:audit_ledger.jsonl` locks. | **P2 (Ledger Write Contention)** |

---

## 2. EVALUATION OF INTEGRATION ORDERS

### Candidate Order 1: Current Baseline (`A01 → L01 → G01 → B01`)
- **Stage 1 (A01)**: Central Dispatcher Uncertainty Fence installed first. Closes the most dangerous production defect (duplicate redispatch under uncertainty). Completely self-contained; depends on zero other new schemas.
- **Stage 2 (L01)**: Hierarchical and Semantic Resource Locking installed next. Prevents concurrent writer collisions across parent/child folders. Works cleanly on top of A01.
- **Stage 3 (G01)**: Deferred Liability & Capability Gate installed third. Safely relies on A01 fence to guarantee that unsettled financial transactions never redispatch.
- **Stage 4 (B01)**: Multi-Factor Process Identity installed last after Darwin Mac-native validation on physical hardware.
- **Safety Assessment**: **MAXIMALLY SAFE**. Every stage provides positive monotonically increasing security with zero regression windows.

### Candidate Order 2: Inverted Order (`B01 → G01 → L01 → A01`)
- **Flaw**: B01 requires Mac hardware proof, which blocks all integration until Mac freeze is lifted. Installing G01 without A01 creates the P0 financial retry vulnerability.
- **Verdict**: **REJECTED (Unsafe & Blocked)**.

### Candidate Order 3: Grouped Atomic Deployment (`[A01 + L01 + G01 + B01] in a single commit`)
- **Flaw**: Single large diff increases blast radius and conflates pure Node control-plane changes (A01, L01, G01) with platform-specific Darwin kernel calls (B01).
- **Verdict**: **REJECTED**.

---

## 3. RECOMMENDED INTEGRATION ORDER

$$\mathbf{A01} \longrightarrow \mathbf{L01} \longrightarrow \mathbf{G01} \longrightarrow \mathbf{B01}$$

- **Has the order changed from A01 → L01 → G01 → B01?**: **NO**.
- **Why**:
  1. A01 has zero external dependencies and eliminates the highest-severity failure mode (P0 duplicate execution under uncertainty).
  2. G01 strictly requires A01 to be active before financial gating can be fully sound against crash recovery loops.
  3. L01 is completely independent of B01 when legacy lease timeouts are preserved as fallback.
  4. B01 is the ONLY invariant requiring physical Mac Darwin hardware validation; placing it last prevents holding back the three purely software-provable invariants.

---

## 4. PARTIAL-INTEGRATION STATE ATTACK MATRIX

| State Combination | Attack Scenario | System Response Under Staged Architecture | Safety Outcome |
|---|---|---|---|
| **A01 installed, L01 old** | Two tasks target `src/` and `src/core/` concurrently. | `no_stacking.js` allows concurrent dispatch; however, if either crashes, A01 blocks redispatch. | **PARTIALLY SAFE** (Resource collision possible; duplicate execution blocked) |
| **A01 + L01 installed, G01 old** | Agent executes "14-day free trial with auto-renew €50". | Naive `price_eur <= 0` passes spend gate; however, L01 prevents simultaneous ledger writes, and A01 prevents retry if checkout fails. | **PARTIALLY SAFE** (Financial liability possible; code/data corruption blocked) |
| **G01 installed before A01** | Financial checkout fails midway; network drops; worker restarts. | Without A01, Router sees dead lease and redispatches payment request, charging user twice. | **UNSAFE VIOLATION** (Proves G01 must NEVER precede A01) |
| **B01 installed without migration** | Reconciler inspects legacy lease lacking `start_time_epoch_ms`. | Reconciler treats missing field as `UNKNOWN`, fails closed, never kills process, and flags for manual review. | **SAFE (Fail-Closed)** |
