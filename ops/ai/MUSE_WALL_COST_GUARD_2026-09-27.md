# Muse Wall Cost Guard Policy

## 1. Core Principles
The Muse Wall Cost Guard enforces strict economic and performance limits on execution. It guarantees that independent agents and verifiers do not consume unbounded resources.

### Hard Constraints
- **MINIMUM_NECESSARY_READS**: Context must be narrow. Target explicit paths or functions rather than traversing directories.
- **NO_BROAD_REPO_SCAN**: Unbounded or wildcard repository scans (e.g. naive embeddings generation without scope) are explicitly prohibited.
- **NO_REPEATED_UNCHANGED_READS**: Context snapshots must be checkpointed. Identical inputs must read from the cache rather than invoking external model or API queries.
- **NO_IDLE_ANALYSIS**: AI instances must halt and hibernate if no actionable `READY` work exists. Speculative generation of non-critical-path work is blocked.
- **NO_DUPLICATE_WORK**: Every execution is checked against the central `DO_NOT_REPEAT` ledger fingerprint.
- **RESULT_REUSE_FIRST**: Before issuing any network request or motor invocation, existing `DurableResult` objects must be reused if the hash and contract match.
- **QUEUE_EMPTY => IDLE/STOP**: The default behavior upon exhaustion of `QUEUED` and `READY` items is to enter durable suspension (`IDLE/STOP`).

## 2. Capacity & Budgeting Rules

### Subscription-First Auto-Routing
All workloads MUST route through predefined subscription capacity first. 
- Only after subscription allocation is 100% utilized and queuing latency exceeds the allowable threshold may PAYG (Pay-As-You-Go) pipelines activate.
- PAYG routing MUST be explicitly enabled by the workflow context and MUST remain under the hard-capped daily budget.

### Idempotency Across Sessions
- **Session Independence**: Re-authenticating, restarting the daemon, or changing the account session MUST NOT reset the ledger.
- Existing ledger state and `DurableResult` identities govern execution. A restarted session resuming a `RECONCILED` task MUST reuse the result rather than repeating it.

## 3. Device-Adaptive Motor Admission

Motor concurrent execution is dynamically throttled by device health telemetry.
- **Wall 10 Health Guard**: Total parallel motor admission is not fixed. 
- Depending on available memory pressure, CPU thermals, and I/O saturation, the system may dynamically constrain active motors to 4, 5, 6, 8, 9, or other safe thresholds. 
- Motors exceeding the health threshold must remain in the `REQUESTED` state and will not be `ADMITTED` until resources free up.
