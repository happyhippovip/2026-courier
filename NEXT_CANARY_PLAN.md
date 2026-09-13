# NEXT CANARY PLAN: POST-INTEGRATION COURIER AUTONOMY

## 1. Context & Boundaries
With the core autonomy plane verified in production (`114/114 tests PASS`), the system is mechanically capable of running multi-hour autonomous loops without premature termination or uncoordinated process destruction.

**CRITICAL MANDATE**:
- Autonomous spend limit remains strictly **€0.00**.
- Real trading is strictly **0**.
- Real wallet signing is strictly **DISCONNECTED / NO**.
- Any live financial transaction requires explicit human sign-off via **`HUMAN_GATE`**.

---

## 2. Bounded Canary Phases

### Phase 1: Local Offline Canary (Synthetic Sandbox)
- **Objective**: Run the integrated supervisor in an extended 1-hour autonomous loop against synthetic opportunity streams.
- **Verification Gates**:
  1. `ResourceLockManager` prevents all synthetic subpath write collisions.
  2. `ProcessLeaseManager` maintains heartbeat and process lifecycle without false kills.
  3. `BorderGuard` issues cryptographically signed `TaskPassport` for each synthetic simulation.
  4. `ResultCustoms` verifies simulated PnL artifacts and disk SHA-256 checksums.
  5. `CompletionGovernor` admits verified units to offline ledger without early termination.
- **Target Metrics**:
  - Zero crashes.
  - Zero hung processes.
  - Zero premature exits.
  - Spend: €0.00.

### Phase 2: Read-Only Market Intake Canary
- **Objective**: Connect read-only public market price feeds to Opportunity Warehouse.
- **Boundary**: Ingestion only; no outbound trading or private key access.
- **Verification**: Ensure opportunity discovery adheres to anti-loop policy and deduplication.

### Phase 3: Simulated First €5 Generation (Paper Execution)
- **Objective**: Execute end-to-end simulated trade to produce €5 synthetic gain.
- **Boundary**: Uses `First5EuroSimulator` with complete audit envelope.
- **Transition to Live**: Strictly held at `HUMAN-GATE-003`. Live funds require manual human key entry and explicit authorization.

---

## 3. Immediate Next Steps for Chief
1. Review uncommitted git diff in `courier/supervisor/`.
2. Inspect `PRODUCTION_INTEGRATION_REPORT.md` and `SAFETY_VERIFICATION.json`.
3. Commit integration patch with commit message:
   `feat(supervisor): integrate durable autonomy runtime choke points (GAP-001..GAP-005)`
