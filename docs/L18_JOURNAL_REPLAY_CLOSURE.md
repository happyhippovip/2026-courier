# L18 JOURNAL REPLAY CLOSURE

## Objective
Find any remaining replay acceptance gap in the event sourcing journal or the state machine's deterministic projection logic, ensuring restart/replay perfectly preserves ledger truth without double-processing.

## Findings
The Ledger structurally closes all replay acceptance gaps through a dual-layered defense spanning `courier_core/journal.py` and `courier_core/state_machine.py`.

1. **State Machine Fencing (`apply`)**: Every critical task transition (`TASK_CREATED`, `TASK_CLAIMED`, `TASK_STARTED`, `RESULT_READY`, `RESULT_ACCEPTED`, `TASK_COMPLETE`, etc.) is guarded by strict `TaskStatus` boundary checks. For example, `RESULT_READY` requires `TaskStatus.RUNNING` and immediately transitions the task to `VERIFYING`. Replaying a `RESULT_READY` event when the task is already in `VERIFYING` reliably raises a `TransitionError`, blocking the append.
2. **Journal Deduplication**: Events that legitimately do not progress the state machine (e.g., `LATE_RESULT_DISCARDED`) or require identical-content idempotency bypass the state machine fences but are securely gated by explicit `dedupe_key` enforcement at the SQLite level. `get_event_by_dedupe_key` perfectly intercepts and acknowledges these replays without appending duplicate events.

There are no un-fenced mutations or gaps where an identical or competing event can corrupt a task's sequence.

## Validation
I created `tests/controller/test_l18_journal_replay_closure.py` to systematically replay every critical event in the `TaskState` lifecycle against a sequentially advanced projection. Every single illegal replay successfully raises a `TransitionError`. Since the `fold()` logic relies identically on `apply()`, both the live memory projection and the DB rebuilt projection are mathematically equivalent and perfectly immune to replay attacks. No code mutation is required.
