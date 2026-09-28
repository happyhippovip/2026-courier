# Local Taskbank Replenisher Execute Patch

Problem:
The old replenisher generated READY tasks and then backed off, leaving work unexecuted.

New invariant:
READY_WORK_GENERATED => EXECUTE_NEXT_CHILD immediately.

Forbidden:
READY_WORK_GENERATED -> TEMPORARY_IDLE

Required:
READY_WORK_GENERATED -> CLAIM_CHILD -> EXECUTE -> RESULT -> NEXT_CHILD

TEMPORARY_IDLE is legal only when READY_COUNT=0 after harvest, synthesis, preparation, blocker decomposition, and cross-family check.
