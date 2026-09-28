# Courier Physical Canary Proof Bundle (Mac Host)
**Date:** 2026-09-27  
**Host:** MAC (Darwin x86_64/arm64)  
**Provider:** GOOGLE  
**Staging Coordinator:** `http://127.0.0.1:8081`  
**Production Isolation:** Port 8080 completely untouched (PID 69407)  
**Human Relay Count:** 0 (ZERO)  
**Overall Verdict:** PASS  

---

## 1. Executive Summary

This proof bundle provides physical, verifiable operational and cryptographic proof of the Courier Symphony end-to-end execution pipeline on the Mac host:
1. **PHYS-001:** Staging server isolation and port binding on Port 8081 without collision or disturbance of production Port 8080.
2. **PHYS-002 (RUN_1 Canary Pass):** Full A -> VERIFY -> B flow. Worker execution -> artifact byte upload -> server-side artifact store hashing -> independent verifier confirmation -> automatic dispatch of dependent step -> zero human relay.
3. **PHYS-003 (RUN_2 Restart Persistence & Replay Gate):** Coordinator hard process termination (SIGTERM) mid-workflow -> coordinator restart -> durable state preservation -> zero replay of reconciled tasks (`attempts == 1`) -> seamless auto-dispatch and completion of subsequent workflow steps.
4. **PHYS-004:** Cryptographic attestation, ledger reconciliation, and publish staging.

---

## 2. Test Execution Details

### A. PHYS-001: Staging Server Binding & Isolation
- **Endpoint:** `http://127.0.0.1:8081`
- **State Root:** `/Users/user/courier_work/canary_run1/state/central_state.json`
- **Artifact Store:** `/Users/user/courier_work/canary_run1/artifact-store`
- **Responses:**
  - `GET /health` -> `HTTP 200` (`status: healthy`)
  - `GET /status` (Authenticated) -> `HTTP 200`
- **Isolation Check:** Port 8080 production server remained active and responsive throughout.

### B. PHYS-002: RUN_1 Canary Execution (A -> VERIFY -> B)
- **Goal ID:** `goal-d0a02c0e`
- **Step A (`canary-task-a`):**
  - Claimed by: `CANARY-MAC-01` (`attempts: 1`, `dispatch_id: dispatch-d460fe7b11854be0941bf2a62c3b7110`)
  - Artifact Upload: `artifact-a.txt` -> server store returned `art-32339451dabe1c71bcbb9b9dde4debbaacab94b411e31058987b053ae76329ea`
  - Upload SHA-256: `89828ee566fc9dd853bd3fffd65f9bd4b834d56b6e5a70fcc62c99dfc1bce07b`
  - Verifier: `VERIFIER-CANARY-01` fetched server artifact bytes, re-hashed, confirmed exact SHA-256 match.
  - Verdict: `PASS` posted to `/tasks/verify` -> status transitioned to `RECONCILED`.
- **Step B (`canary-task-b`):**
  - Trigger: Auto-dispatched by coordinator immediately upon Step A reconciliation.
  - Claimed by: `CANARY-MAC-01` (`attempts: 1`)
  - Artifact Upload: `artifact-b.txt` -> `art-cb0456bc32d0a27cb0e083d4418d12191a79434925f9b4980717c7bc687c72a1`
  - Upload SHA-256: `8ce1105ea18f216be82958600d2c67366c73f279409059f1a6a60c503a910615`
  - Verifier: Confirmed server copy hash match -> verdict `PASS` -> `RECONCILED`.
- **Goal Completion:** `goal-d0a02c0e` reached `DONE`.
- **Evidence Artifact:** `/Users/user/courier_work/canary_run1/run1_proof.json`

### C. PHYS-003: RUN_2 Controlled Restart & Replay Gate
- **Pre-Restart State:** `canary-task-a` durably preserved in JSON state with `attempts == 1` and `RECONCILED`.
- **Goal ID:** `goal-48da855c`
- **Step A (`run2-task-a`):**
  - Executed, uploaded `artifact-2a.txt`, independently verified, status marked `RECONCILED` (`attempts == 1`).
- **Simulated Crash / Restart:**
  - Coordinator process killed via `SIGTERM`.
  - Staging coordinator restarted on Port 8081 with fresh PID (PID 15728) reloading state file.
- **Post-Restart Integrity Verification:**
  - Query `/goals/goal-48da855c`: `run2-task-a` retained `RECONCILED` status; `attempts` remained strictly `1`.
  - Next task claim: Coordinator returned `run2-task-b` (`status: QUEUED`). Zero replay of `run2-task-a` occurred.
- **Step B (`run2-task-b`):**
  - Executed post-restart, uploaded `artifact-2b.txt`, verifier confirmed match, status marked `RECONCILED` (`attempts == 1`).
  - Goal completed post-restart.
- **Evidence Artifact:** `/Users/user/courier_work/canary_run1/run2_proof.json`

---

## 3. Cryptographic & Operational Ledger Attestation

| Task ID | Action | Fingerprint | Verdict | Status |
|---|---|---|---|---|
| `PHYS-001` | Staging Server Binding & Isolation | `phys-staging-bind-001` | PASS | RECONCILED |
| `PHYS-002` | RUN_1 Canary Pass (A -> VERIFY -> B) | `phys-run1-canary-002` | PASS | RECONCILED |
| `PHYS-003` | RUN_2 Restart Persistence & Replay Gate | `phys-run2-restart-gate-003` | PASS | RECONCILED |
| `PHYS-004` | Proof Bundle Attestation & Evidence Export | `phys-bundle-attest-004` | PASS | RECONCILED |

**Total Human Relays:** 0  
**Repository Source Tree Modification:** 0 lines (strict zero-write discipline on Mac host)
