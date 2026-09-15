# PROCESS SAFETY THREAT MODEL

## Overview
Autonomous agents pose unique operational risks due to their ability to execute arbitrary commands rapidly while lacking inherent state tracking across reasoning loops. This threat model identifies how agents inadvertently harm host infrastructure and details the architectural mitigations.

| Threat | Description | Vector | Mitigation Requirement |
|---|---|---|---|
| **Ghost Task Exhaustion** | Agent spawns `tail`, tests, or servers and forgets to terminate them before finishing. | `subprocess.Popen` without wait/block. | Req 15 (Agent Drain Barrier), Req 1 (Canonical Spawn Gate). |
| **Silent Process Escape** | Grandchild process outlives parent, daemonizing into the background. | `shell=True`, double-forking. | Req 6 (PGID / Windows Job Object Containment). |
| **PID Reuse Collisions** | System reassigns a PID to a foreign process; watchdog kills it. | OS PID exhaustion/wrap-around. | Req 5 (Strong Identity: PGID + Start Time + Executable). |
| **Foreign Process Assassination** | Watchdog uses `pkill` or substring matching, killing a human's process. | Greedy cleanup scripts. | Req 13 (No Blind Kills), Req 40.I2 (Provable Ownership required for kill). |
| **Reboot Split-Brain** | Machine reboots; supervisor blindly restarts stale processes from DB. | Ledger state desync. | Req 25 (Startup Reconciliation: QUARANTINE state). |
| **Remote Execution Orphan** | Network drops, local SSH client dies, remote heavy workload runs forever. | Network partition. | Req 16 (Remote Execution Durable ID & independent reconciliation). |
| **Partial Artifact Corruption** | Agent killed mid-download, leaving a corrupt `.zip` that subsequent steps trust. | Pre-mature termination. | Req 17 (Downloads use `.tmp` + Atomic rename). |
| **Time Travel Deadlocks** | Laptop sleeps or DST changes; timeouts calculated via wall-clock drift. | NTP / Sleep cycles. | Req 9 (Monotonic Elapsed-Time budgets). |
| **Pipe Buffer Deadlock** | Child spits 2GB of logs; OS pipe buffer fills, blocking child and supervisor. | `capture_output=True` on unbounded streams. | Req 18 (Pipe Backpressure / Bounded limits). |
| **Agent Retry Storms** | Intermittent API error causes agent to spawn 50 concurrent validation scripts. | Unbounded reasoning loops. | Req 20 (Agent Fanout), Req 21 (Circuit Breaker). |
| **Secret Exfiltration** | Child process environment variables leak GitHub tokens into logs. | Inherited `os.environ`. | Req 23 (Secret Safety / Env Allowlisting). |
| **Unbounded Recovery** | System doesn't know if a side-effect completed before crashing, so it retries. | Crash during execution. | Req 11 (Unknown Effect Quarantine), Req 12 (Result Fencing). |
