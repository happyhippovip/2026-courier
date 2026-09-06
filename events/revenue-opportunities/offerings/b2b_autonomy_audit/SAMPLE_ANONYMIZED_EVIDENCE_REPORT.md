# Sample Synthetic Audit Evidence Report
*(Delivery Process Specification Sample — For Demonstration Only — No Real Customer History)*

**Target Workflow:** Autonomous Python Agent Runner (Local Subprocess Batch Engine)  
**Evaluation Date:** 2026-09-01  
**Assessment SLA:** 48 Hours | **Price Reference:** €99 Fixed Scope  

---

## 10-Point Determinism Matrix Results

| ID | Check Description | Status | Evidence & Observation |
|:---|:---|:---|:---|
| **C-01** | POSIX File Fencing & Split-Brain | `FAIL` | Manual JSON lock file orphaned on `SIGKILL`; no POSIX flock leasing |
| **C-02** | Process Liveness Truth | `FAIL` | Dead worker assumed alive from un-updated heartbeat log; no PID kill 0 check |
| **C-03** | Reboot Crash Recovery | `PASS` | State ledger parsed cleanly after process restart |
| **C-04** | Heartbeat Staleness Detection | `FAIL` | No max heartbeat gap alarm; stalled worker ran indefinitely |
| **C-05** | Quota & Spend Firewall | `PASS` | Hard 0.00 EUR local spend limit enforced |
| **C-06** | Permission Loop Breaker | `PASS` | Subprocess stdin connected to devnull; no interactive prompt hangs |
| **C-07** | Idempotent Side-Effect Boundaries | `FAIL` | Retrying failed batch re-applies non-idempotent file appends |
| **C-08** | State File Corruption Protection | `FAIL` | Zero-byte state file triggers unhandled JSONDecodeError |
| **C-09** | Monotonic Epoch Fencing | `PASS` | Generation tokens increment monotonically |
| **C-10** | Fail-Closed Default Posture | `UNKNOWN` | Insufficient safe evidence on unhandled OS exceptions |

---

## Prioritized Remediation Plan
1. **[CRITICAL] Atomic File Fencing:** Replace manual lock file with kernel-level `fcntl.flock()`.
2. **[HIGH] Kernel PID Verification:** Implement `os.kill(pid, 0)` before asserting worker progress.
3. **[MEDIUM] Zero-Byte State Hardening:** Add atomic replace pattern (`os.replace`) to prevent zero-byte corruptions.
4. **[LOW] Idempotency Keys:** Wrap task side-effects in SHA-256 completion fingerprints.

---

## Deliverable Proof Artifacts
- `harness/test_reproducible_crash_proof.py`: 3 unit tests reproducing the lock stall and verifying the fix.
- `src/canonical_authority.py`: 80-line drop-in reference lock manager.
