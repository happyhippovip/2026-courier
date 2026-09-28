# MAC-HNI-23 — Pilot Packet Preparation (Gated Behind Core Freeze)

## 1. Overview & Operational Authority
- **Task ID**: MAC_HNI_23
- **Area**: PILOT_PACKET_PREP
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE
- **Gate Precondition**: Strictly gated behind Core Freeze certification.

---

## 2. Pilot Scope & Governance Boundary
- **Objective**: Establish the formal pilot onboarding, participant consent, telemetry instrumentation, and verification criteria for initial external operator testing.
- **Prerequisite Enforcement**:
  - `CORE_FREEZE_STATUS=CERTIFIED` required before any pilot participant invitation or deployment.
  - Zero application source mutation permitted during pilot execution.
- **Participant Sandboxing**:
  - Isolated staging environments with local-only file system bounds.
  - Zero production database write access.
  - Cryptographic token authentication for all telemetry and state reporting.

---

## 3. Participant Consent & Privacy Protection Contract
1. **Informed Consent**: Explicit opt-in required prior to dispatching coordinator agents.
2. **Data Minimization**:
   - Zero capture of ambient user keystrokes, personal file trees, or system credentials.
   - Telemetry limited to: task execution IDs, process exit codes, memory high-water marks, and SHA-256 block hashes.
3. **Revocation Rights**: Operator may terminate session immediately via standard POSIX signal (`SIGTERM` / `SIGINT`), initiating clean state flush and lock release.

---

## 4. Key Performance Indicators & Measurement Metrics
| Metric | Target Threshold | Falsification / Failure Condition |
| :--- | :--- | :--- |
| **Autonomy Grade** | `Grade A4` (100% Zero-Relay) | Any manual human intervention event |
| **Idempotent Restart Rate** | 100% success on 12-case matrix | Re-execution of Task A or state loss |
| **Ledger Verification Time**| < 15ms per block attestation | > 100ms or cryptographic mismatch |
| **Memory Footprint** | < 256 MB per worker | Process memory > 512 MB |
| **Crash Recovery Latency** | < 2.0s post-SIGKILL | > 5.0s or orphaned PID file lock |

---

## 5. Formal Verification Contract
```python
def verify_pilot_readiness(core_freeze_certified: bool, telemetry_schema_valid: bool) -> bool:
    assert core_freeze_certified, "Pilot cannot proceed prior to complete Core Freeze certification."
    assert telemetry_schema_valid, "Telemetry schema must be fully validated against data privacy rules."
    return True
```

---

## 6. Integration Verdict
- **Deliverable**: `ops/ai/mac_finish24/deliverables/MAC_HNI_23_PILOT_PACKET_PREP.md`
- **Blocker**: NONE
- **Missing**: NONE
- **Next Exact Action**: Advance to `MAC_HNI_24` (Product Shell Gate).
- **Do-Not-Repeat Fingerprint**: `MAC_HNI_23:COMPLETE:ops/ai/mac_finish24/deliverables/MAC_HNI_23_PILOT_PACKET_PREP.md`
