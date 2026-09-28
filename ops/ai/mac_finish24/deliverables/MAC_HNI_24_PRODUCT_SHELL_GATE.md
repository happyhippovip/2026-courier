# MAC-HNI-24 — Product Shell Evidence Gate Specification

## 1. Overview & Operational Authority
- **Task ID**: MAC_HNI_24
- **Area**: PRODUCT_SHELL_GATE_PACKET
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE
- **Product Gate Status**: HARD_LOCKED (Awaiting Durable Positive Real-Pilot Evidence)

---

## 2. Invariant Gate Laws
1. **Core Freeze Prerequisite**: `CORE_FREEZE_DECLARED=YES` and verified by independent cryptographic attestation.
2. **Real-Pilot Evidence Required**: Under no circumstances may the commercial Product Shell or packaging activate on simulated, synthetic, or mock telemetry.
3. **Zero P0/P1 Defects**: The real pilot deployment must complete with 0 unresolved P0/P1 incidents, 0 state regressions, and 0 manual human relay interventions.
4. **Idempotence & Autonomy**: Pilot operators must achieve Grade A4 autonomy with 100% crash recovery and zero duplicate task dispatches.

---

## 3. Product Shell Lock Matrix
| Component / Layer | State Before Pilot | Unlocking Trigger | Failure Mode / Lockdown |
| :--- | :--- | :--- | :--- |
| **CLI User Interface** | Internal Dev Harness Only | Verified Pilot Completion Report | Lock to Dev Mode |
| **Telemetry Ingestion** | Local Sandbox Only | Signed Opt-in Pilot Consents | Reject Unsigned Ingestion |
| **Billing / Packaging** | Disabled / Non-existent | Business Stakeholder Authorization | Hard Block |
| **Update Distribution** | Local Git Branch Only | Tagged Release Signed by Core Freeze | Prohibit Auto-Update |

---

## 4. Formal Verification Gate Logic
```python
def evaluate_product_shell_gate(
    core_freeze_certified: bool,
    real_pilot_completed: bool,
    pilot_success_rate: float,
    unresolved_p0_p1_count: int,
    zero_relay_verified: bool
) -> bool:
    """
    Evaluates whether the commercial Product Shell gate can transition from LOCKED to UNLOCKED.
    """
    if not core_freeze_certified:
        return False
    if not real_pilot_completed:
        return False
    if pilot_success_rate < 0.995:
        return False
    if unresolved_p0_p1_count > 0:
        return False
    if not zero_relay_verified:
        return False
    return True
```

---

## 5. Integration Verdict
- **Deliverable**: `ops/ai/mac_finish24/deliverables/MAC_HNI_24_PRODUCT_SHELL_GATE.md`
- **Blocker**: PRODUCT_SHELL_HARD_LOCKED (Waiting for physical proof and real pilot execution)
- **Missing**: REAL_PILOT_EVIDENCE
- **Next Exact Action**: ALL_HNI_24_PREP_COMPLETE -> HARVEST_AND_RECONCILE
- **Do-Not-Repeat Fingerprint**: `MAC_HNI_24:COMPLETE:ops/ai/mac_finish24/deliverables/MAC_HNI_24_PRODUCT_SHELL_GATE.md`
