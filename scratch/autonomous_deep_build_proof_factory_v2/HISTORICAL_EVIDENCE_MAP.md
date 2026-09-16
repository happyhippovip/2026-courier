# HISTORICAL EVIDENCE MAP

**MISSION ID**: `WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2`  
**STATUS**: `SEALED HISTORICAL BASELINES (READ-ONLY)`  

---

## 1. HISTORICAL WINDOWS MISSION ROOTS

The following directories represent sealed historical baselines. They must not be modified, overwritten, or rerun, but serve as foundational evidence:

1. **RC3 Frozen Baseline**:
   - Location: `C:\Users\lol\2026-workspace\handoffs\COURIER_HANDOFF_RC3`
   - Hardening Tests: `C:\Users\lol\2026-workspace\courier\tests\rc3_hardening\`
   - SHA-256: `739fe3d87af99a65b43ffb6ef53c47ebefcb6602448ace95fc7dd13dd3435cd4`
   - Role: Read-only release candidate baseline.

2. **V2 Deep Engineering Lab**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\autonomous_deep_engineering_v2\`
   - Role: 315 passing tests establishing basic dispatcher, reconciler, and gate contracts.

3. **V3 Integration Certification Factory**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\integration_certification_factory_v3\`
   - Role: 498 passing certification tests verifying release readiness.

4. **Final High Value Sweep V1**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\final_high_value_quota_sweep_v1\`
   - Role: Targeted bounded sweep of Windows-only invariants.

5. **Final 4% Adversarial Sweep V1**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\final_4pct_adversarial_intervention_v1\`
   - Role: Identification of four core defects: A01, L01, G01, B01.

6. **Nightshift Adversarial Factory V5**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\nightshift_adversarial_factory_v5\`
   - Role: 130 passing adversarial suites and 33 minimized counterexamples.

7. **Final Integration Red-Team Pack V1**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\final_integration_redteam_pack_v1\`
   - Role: 24/24 red-team attacks validating A01, L01, G01, B01 candidate modules.

8. **Autonomous Overnight Portfolio V1**:
   - Location: `C:\Users\lol\2026-workspace\courier\scratch\autonomous_overnight_portfolio_v1\`
   - Role: 115 passing tests across 10 campaigns, 29 mutants killed, 10 minimized counterexamples, establishing the baseline for autonomous long-run operation.

---

## 2. SYNTHESIS OF CORE PROVED INVARIANTS

| Defect Code | Core Vulnerability | Proven Solution in Shadow |
|---|---|---|
| **A01** | Indirect uncertain fallback redispatch | Centralized `DispatcherUncertaintyFence` dominating all retry/reroute paths |
| **L01** | Hierarchical writer path collision | `AdvancedNoStackingMutex` with path canonicalization & prefix locking |
| **G01** | Deferred recurring subscription spend trap | `ZeroSpendBoundaryGovernor` checking immediate & future liabilities |
| **B01** | PID recycling & process identity confusion | Tri-state process oracle (`MATCH`, `MISMATCH`, `UNKNOWN`) with start-time verification |
| **I01** | Worker false-satisfaction reporting | Cryptographic `GoalSatisfactionEnvelope` with independent assertion verification |
| **T01** | Cross-workstream circular wait deadlocks | `DependencyCycleAndDeadlockResolver` wait-for graph cycle breaker |
