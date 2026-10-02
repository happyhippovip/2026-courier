# L15 LATE RESULT FENCING

## Objective
Attack stale worker/write-after-transfer paths to see if a late worker can corrupt a task that has been transferred to a new worker.

## Findings
The system is structurally protected against write-after-transfer (stale worker) attacks by the strict identity of `dispatch_id`. 

When a task's lease expires and it is reclaimed (via `tick()` -> `_decide()`), its state transitions from `RUNNING` -> `RETRY_PENDING` -> `QUEUED`. When a new worker claims the task, the controller generates a completely new, cryptographically unique `dispatch_id`. 

If the original (stale) worker completes the task and attempts a `POST /result` with the old `dispatch_id`, the controller explicitly fences the request:
```python
if task.dispatch_id == dispatch_id and task.status is TaskStatus.RUNNING:
    ...
```
Since the `dispatch_id` no longer matches the current active attempt in the journal, this condition evaluates to `False`. The controller harmlessly records the event as `LATE_RESULT_DISCARDED` (incrementing the task's `late_results` metric) and rejects the HTTP request with `409 stale_dispatch`.

The stale worker's result is permanently fenced off and does not affect the active attempt by the new worker.

## Validation
I have created a rigorous test suite `tests/controller/test_l15_late_result_fencing.py` to pin this contract. The test explicitly simulates a lease expiration, a transfer to a second worker, a write-after-transfer attack by the first worker, and validates that the second worker remains completely uncorrupted. No implementation fixes are required.
