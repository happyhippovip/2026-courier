# BATCH G5: REAL LEDGER / MOTOR WORK HARVEST

## 1. Motor Thread Exception Swallow
**BUG:** When `future.result()` raises an unhandled Exception (e.g., a crash inside `execute_task`), the motor loop in `main()` catches it but only adds the task to `blocked_tasks_this_run`. It never calls `update_ledger` to record the blocker. As a result, the ledger remains `RUNNING` or `READY`, the failure is permanently lost across restarts, and the Motor is infinitely wedged.
**EXECUTABLE EVIDENCE:** `test_motor_crash_swallow.py` successfully demonstrates the absence of `update_ledger` in the exception handler.
**EXACT_FILE:** `scripts/courier_continue.py`
**EXACT_FUNCTION:** `main()` (specifically the `try...except Exception as e:` block for `future.result()`)
**MINIMAL REPRODUCER:** Run an `execute_task` that raises `RuntimeError`. Watch Motor exit without mutating `agent_handoff_ledger.json`.
**EXPECTED INVARIANT:** ONE CRASHED TASK MUST RECORD ITS BLOCKED STATE IN THE LEDGER.
**NEGATIVE TEST:** Healthy tasks correctly call `update_ledger(..., new_blocker, ...)`.
**TARGETED TEST:** `test_motor_crash_swallow.py`
**OWNER:** Google (Motor owner)
**DEPENDENCIES:** Ledger update flow.

## 2. Server Infinite Retry Loop on MAX_RETRIES
**BUG:** When `retry_state["execution"] >= MAX_RETRIES["execution"]`, `task_result()` fails to transition the task to `FAILED_TERMINAL`. Instead, it resets `retry_state["execution"] = 0` and sets the status back to `"QUEUED"`. This creates an infinite retry loop for persistently failing tasks.
**EXECUTABLE EVIDENCE:** `test_server_infinite_retry.py` successfully parses the AST to prove `retry_state['execution'] = 0` happens on the max retries `else` branch.
**EXACT_FILE:** `server/app.py`
**EXACT_FUNCTION:** `task_result()` (and similarly `task_verify()`)
**MINIMAL REPRODUCER:** Submit a task that always fails with a generic error (not AMBIGUOUS_CRASH). Wait for it to exceed max attempts and observe it re-queues instead of failing.
**EXPECTED INVARIANT:** Persistent error -> bounded failure -> never infinite hang.
**NEGATIVE TEST:** Tasks that succeed within attempt limits process normally.
**TARGETED TEST:** `test_server_infinite_retry.py`
**OWNER:** Google (Server owner)
**DEPENDENCIES:** None.

## 3. Silent Unblocking of Ledger State
**BUG:** If Task A fails and sets the ledger `STATUS` to `"BLOCKED"`, and concurrently Task B succeeds, `update_ledger` processes Task B's success and unconditionally sets `updates["STATUS"] = "READY"`. This overwrites and destroys the `"BLOCKED"` state of the ledger, hiding the terminal failure of Task A and allowing the motor to improperly continue.
**EXECUTABLE EVIDENCE:** `test_ledger_status_overwrite.py` demonstrates `updates["STATUS"] = "READY"` is assigned without checking if `FIRST_CAUSAL_BLOCKER` is present or if the current status is `BLOCKED`.
**EXACT_FILE:** `scripts/courier_continue.py`
**EXACT_FUNCTION:** `update_ledger()` (the success branch where `blocker` is None)
**MINIMAL REPRODUCER:** Update ledger with a blocker, then update it with a successful task. Observe `STATUS` becomes `"READY"` while `FIRST_CAUSAL_BLOCKER` is still active.
**EXPECTED INVARIANT:** A terminal failure on one branch must not have its `BLOCKED` status overwritten by a successful independent branch.
**NEGATIVE TEST:** An update where `blocker` is provided correctly sets `STATUS = "BLOCKED"`.
**TARGETED TEST:** `test_ledger_status_overwrite.py`
**OWNER:** Google (Ledger owner)
**DEPENDENCIES:** Ledger state machine invariants.
