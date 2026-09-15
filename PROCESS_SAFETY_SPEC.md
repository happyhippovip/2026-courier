# COURIER FULL AUTOMATION: PROCESS SAFETY SPECIFICATION

## Core Invariants
1. **I1**: NO MANAGED WORK EXISTS WITHOUT DURABLE BOUNDED OWNERSHIP.
2. **I2**: NO AUTOMATIC PROCESS TERMINATION WITHOUT PROVABLE OWNERSHIP.
3. **I3**: MAX ONE ACTIVE OWNER PER PROTECTED SCOPE.
4. **I4**: NO TERMINAL AGENT SUCCESS WITH UNRESOLVED NON-PERSISTENT OWNED WORK.
5. **I5**: AMBIGUITY CAUSES NEITHER DUPLICATE START NOR AUTOMATIC KILL.
6. **I6**: NO RETRY OF UNKNOWN SIDE EFFECT WITHOUT RECONCILIATION/IDEMPOTENCY.
7. **I7**: NO NEW PRODUCTION SPAWN PATH MAY BYPASS THE CANONICAL GATE.

## 1. Architectural Boundaries
* **Canonical Spawn Gate (Req 1):** All subprocesses, shell commands, and remote executions MUST be routed through a single API interface. A static CI check (Req 34) enforces this across the repository.
* **Supervisor Singleton (Req 2):** Atomic locks guarantee exactly one active supervisor generation per host to prevent split-brain.
* **Service Lifecycle (Req 3):** The Supervisor itself is bounded by `launchd` (Mac) or Windows Services, utilizing native restart backoffs and safe modes.

## 2. Ledger and Identity
* **Durable Ledger (Req 4, 35):** A local, schema-versioned, crash-recoverable database (SQLite with strict journaling and durability guarantees).
* **Strong Identity (Req 5):** Process identity is a composite of `PID + PGID/JobObject + Start Time + Executable Fingerprint + Task ID + Attempt ID + Owner Generation`.
* **Tree Containment (Req 6, 7):** OS-level containment via POSIX Process Groups or Windows Job Objects (explicitly preventing breakaway jobs). FD inheritance is strictly banned.

## 3. Time, Budget, and Termination
* **Monotonic Budgets (Req 9):** All timeouts (`EXECUTION`, `IDLE`, `TOTAL_WALL_CLOCK`) use `time.monotonic()` to survive sleep/wake cycles and NTP adjustments.
* **Graceful Termination (Req 13):** `SIGINT/SIGTERM` -> Bounded Grace -> `SIGKILL` to PGID. "Blind kills" via substring or name are strictly banned.
* **Ambiguity Policy (Req 14, 25):** If process state or ownership is ambiguous (e.g., after a crash or network loss), the system must QUARANTINE and NEVER duplicate start or kill.

## 4. Workload Semantics
* **Agent Drain Barrier (Req 15):** The framework refuses a terminal turn from an AI agent if unowned descendant processes or un-promoted artifacts exist.
* **SSH & Downloads (Req 16, 17):** Remote SSH executions must be reconciled independently of local SSH clients. Downloads must write to `.tmp` files and atomically rename upon completion.
* **Non-Interactive (Req 8):** Automation must fail closed if waiting on unexpected stdin/UAC/sudo prompts.
* **Sockets (Req 27):** Temporary listeners are tied to the lifecycle ledger and block agent termination until closed.

## 5. System Limits
* **Admission Control (Req 19, 36):** Hard limits on CPU concurrency, memory pressure, and queue depth. Rejections happen *before* `fork()`. 
* **Agent Fanout (Req 20):** Bounded recursion and max attempts to prevent worker explosion.
* **Resource Safety (Req 22, 23, 24):** Filesystem limits (disk-full checks), secret-free environment propagation, and least-privilege enforcement.

## 6. Observability
* **Forensics (Req 28, 29):** Every state transition is recorded for SRE auditability. Safe mode (Req 30) prevents new work while preserving this evidence.
* **Backpressure (Req 18):** `stdout/stderr` pipes are strictly bounded/rotated to prevent IO deadlocks.

## 7. GitHub Guardrails (Req 31-33)
* GitHub runners require timeouts, least-privilege `GITHUB_TOKEN`s, PR-only mutations, and separation between Worker and Verifier roles.
