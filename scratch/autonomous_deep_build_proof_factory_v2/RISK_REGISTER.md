# RISK REGISTER: AUTONOMOUS DEEP BUILD FACTORY V2

| Risk ID | Category | Risk Description | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|---|---|
| **RSK-01** | Safety | Accidental financial liability via trial auto-renew | CRITICAL | LOW | `ZeroSpendBoundaryGovernor` multi-phase checks on both immediate spend and recurring obligations. |
| **RSK-02** | Integrity | False satisfaction claims by compromised or buggy worker | CRITICAL | MEDIUM | `IndependentGoalVerifier` evaluating cryptographic deliverable hashes and assertions. |
| **RSK-03** | Liveness | Cross-workstream circular wait deadlocks in long soak runs | HIGH | MEDIUM | Directed wait-for graph cycle detection with priority-based victim preemption. |
| **RSK-04** | State | Corrupt journal entries or partial writes on crash | HIGH | LOW | Append-only journal with monotonic sequences, sha256 checksums, and truncated tail repair. |
| **RSK-05** | Operational | Notification alert storm during transient failure burst | MEDIUM | HIGH | `HighSignalNotificationReducer` deduplication with sliding-window cooldown and template hashes. |
| **RSK-06** | Concurrency | TOCTOU race between BorderGuard inspection and task dispatch | HIGH | MEDIUM | State versioning and cryptographic task passport binding with immutable timestamps. |
| **RSK-07** | Process | Incorrect process termination due to Windows PID recycling | HIGH | MEDIUM | Tri-state process oracle requiring PID + start-time verification; never kill on `UNKNOWN`. |
