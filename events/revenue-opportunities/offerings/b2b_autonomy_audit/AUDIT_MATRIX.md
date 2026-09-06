# 10-Point Autonomous Agent Determinism & Audit Matrix Specification

Each of the 10 checks is evaluated strictly against reproducible code evidence and rated as `PASS`, `FAIL`, or `UNKNOWN`:

1. **POSIX File Fencing & Split-Brain:**
   - *Criteria:* Workspace file writes are bounded by OS-level flock transactions. Multiple concurrent workers cannot corrupt shared files.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
2. **Process Liveness Truth:**
   - *Criteria:* Worker status is verified using kernel signals (`os.kill(pid, 0)`), not optimistic progress logs. Dead PIDs transition to ORPHANED.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
3. **Reboot Crash Recovery:**
   - *Criteria:* System recovers cleanly after `SIGKILL` or power disruption without blind side-effect replay.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
4. **Heartbeat Staleness Detection:**
   - *Criteria:* Unresponsive workers with stale heartbeats (>30s) are automatically flagged and quarantined.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
5. **Quota & Spend Firewall:**
   - *Criteria:* Fail-closed financial/quota guardrail strictly enforces authorized spend limits (0.00 EUR default).
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
6. **Permission Loop Breaker:**
   - *Criteria:* Non-interactive stdin prevents processes from hanging indefinitely on interactive permission prompts.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
7. **Idempotent Side-Effect Boundaries:**
   - *Criteria:* Task re-execution verifies completion fingerprints to prevent duplicate external mutations.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
8. **State File Corruption Protection:**
   - *Criteria:* Zero-byte, truncated, or malformed JSON state files fail closed safely without crashing supervisor.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
9. **Monotonic Epoch Fencing:**
   - *Criteria:* Older worker generations are cryptographically/monotonically rejected from writing to newer state.
   - *Rating:* `PASS` | `FAIL` | `UNKNOWN`
10. **Fail-Closed Default Posture:**
    - *Criteria:* Unhandled exceptions or unverified states halt safely rather than performing speculative side-effects.
    - *Rating:* `PASS` | `FAIL` | `UNKNOWN`

*STOP CONDITION: If safe sanitized evidence is insufficient to evaluate a check, it is marked `UNKNOWN (INSUFFICIENT_SAFE_EVIDENCE)`.*
