# PROCESS SAFETY ACCEPTANCE MATRIX

| REQ_ID | THREAT | COMPONENT | TEST_ID | FAULT_INJECTION | EXPECTED_EVIDENCE | PASS_CRITERION | STATUS |
|---|---|---|---|---|---|---|---|
| **REQ-1** | Unmanaged Bypass | CI / SpawnGate | T-SPAWN-01 | Inject `subprocess.Popen` in new test file. | OS: Git commit fails. | Static check catches forbidden import. | `NOT_IMPLEMENTED` |
| **REQ-2/3** | Split Brain | Supervisor | T-LIFECYCLE-01 | Start second supervisor manually. | Ledger: Lock conflict. | Second instance exits with ALREADY_RUNNING. | `NOT_IMPLEMENTED` |
| **REQ-4/35** | Ledger Corruption | Ledger | T-DB-01 | Simulate `SQLITE_BUSY` or disk full during lease. | Ledger: Rejects claim. | NO SPAWN occurs. | `NOT_IMPLEMENTED` |
| **REQ-5** | PID Collision | SpawnGate | T-ID-01 | Fake PID reuse with foreign process. | OS: Foreign untouched. | Supervisor ignores foreign process despite PID match. | `NOT_IMPLEMENTED` |
| **REQ-6** | Silent Escape | SpawnGate | T-TREE-01 | Child double-forks to grandchild. | OS: `kill -9 -PGID` | Entire process tree is dead. | `NOT_IMPLEMENTED` |
| **REQ-9** | Time Travel | Watchdog | T-TIME-01 | Adjust OS clock by +2 hours. | OS: Process survives. | Monotonic timer prevents premature termination. | `NOT_IMPLEMENTED` |
| **REQ-13/14** | Foreign Assassin | Watchdog | T-AMBIG-01 | Spawn foreign `tail -f`. | OS: Survives supervisor cleanup. | No kill without ledger entry. | `NOT_IMPLEMENTED` |
| **REQ-15** | Ghost Leak | Agent | T-DRAIN-01 | Agent returns SUCCESS while child is alive. | Ledger: Task Rejected. | Supervisor blocks terminal state. | `NOT_IMPLEMENTED` |
| **REQ-16** | Remote Orphan | SSH_Adapter | T-SSH-01 | Disconnect local network interface mid-SSH. | Ledger: Remote Task QUARANTINE. | Reconciliation required before retry. | `NOT_IMPLEMENTED` |
| **REQ-17** | Corrupt Artifact | Downloader | T-DL-01 | SIGKILL downloader at 50%. | OS: Only `.tmp` file remains. | Final artifact path doesn't exist. | `NOT_IMPLEMENTED` |
| **REQ-18** | Pipe Deadlock | SpawnGate | T-PIPE-01 | Child loops printing indefinitely. | OS: Supervisor alive. | Output truncated; child terminated. | `NOT_IMPLEMENTED` |
| **REQ-19** | Out of Memory | Admission | T-RES-01 | Submit 5 heavy jobs to 1 CPU host. | Ledger: PENDING queue grows. | Spawn gate rejects fork() based on budget. | `NOT_IMPLEMENTED` |
| **REQ-25** | Boot Collision | Ledger | T-BOOT-01 | Restart Supervisor while jobs marked RUNNING. | Ledger: Transitions to QUARANTINED. | No blind restart or kill. | `NOT_IMPLEMENTED` |
| **REQ-37** | Crash Window | Supervisor | T-CRASH-01 | SIGKILL Supervisor exactly after `fork` but before DB commit. | OS: Child orphaned. | Human runbook catches it (Safe mode). | `NOT_IMPLEMENTED` |
| **REQ-40.I7**| Missing Guard | CI | T-INV-07 | General bypass test. | OS: CI Failure. | Zero direct `subprocess` calls in repo. | `NOT_IMPLEMENTED` |

*Note: All items currently show `NOT_IMPLEMENTED`. Certification requires causal evidence transitioning these to `IMPLEMENTED_AND_PROVEN`.*
