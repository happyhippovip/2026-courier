# Automation Wake Coalescing Contract

## Failure Model
Courier must prevent the "unbounded wakeup queue" failure pattern. If an automation scope generates a trigger while an existing execution is still `RUNNING`, V1 MUST NOT queue independent parallel work items or create a pending backlog of identical signals (e.g., `PENDING x 60`). Such queue accumulation causes spawn exhaustion (EMFILE) and stalls forward progress.

## Design Invariants
1. **Bounded Queueing:** At most one active execution per logical automation/effect scope.
2. **Coalescence:** Repeated equivalent wakeups while `RUNNING` COALESCE into a single `DIRTY` / `RECHECK_NEEDED` flag.
3. **Execution Edge:** When an execution finishes, if `RECHECK_NEEDED` is set, one fresh state reconciliation occurs to determine if a subsequent run is actually needed.
4. **Instruction Superseding:** Newer state and meaningful human instructions (e.g., forced overrides) supersede stale pending ones.
5. **Cancellation Authority:** Explicit user cancellation strictly wins over pending queues and running processes.
6. **Resource Exhaustion Backoff:** Resource exhaustion (EMFILE/spawn limits) produces a `RESOURCE_PAUSE` state. It must not aggressively blindly retry or trigger subprocess storms.

## Prototype & Validation
This contract is pinned by the executable deterministic tests in `tests/test_automation_wake_coalescing.py` and the minimal state-machine prototype in `scripts/automation_wake_coalescing.py`.

It does NOT alter current L2/L3/L4 Golden semantics or touch the established `courier_core/state_machine.py`. It explicitly defines the queuing policy that future active automation dispatchers must obey.

## Expected Integration
Future automation controllers should map their trigger queues to this state model (`IDLE` -> `PENDING` -> `RUNNING` -> `IDLE`/`PENDING`) rather than using unbounded lists or parallel thread pools per automation ID.
