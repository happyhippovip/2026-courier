# Windows Central Writer - Batch 7

## Substep 1: Fix Process Leak on Timeout
- **Problem:** When `run_task` raised `subprocess.TimeoutExpired`, it called `process.kill()` which only kills the parent `powershell.exe`, leaving child processes running indefinitely.
- **Fix:** Added `taskkill /F /T /PID` to forcibly kill the entire process tree on Windows.
- **Evidence:** Updated `test_run_task_kills_process_on_timeout` to match `timeout` failure payload. 

## Substep 2: Fix OOM / Max Payload Exhaustion 
- **Problem:** If a script printed massive output to stdout/stderr, `windows_worker/daemon.py` stored it unbounded, causing memory exhaustion and failing the Courier API payload size limits.
- **Fix:** Truncated both stdout and stderr in `run_task` to `[-100000:]`.
- **Evidence:** Added test `test_run_task_truncates_large_output` to `test_windows_worker_contract.py` which mocks `process.communicate` to return 150KB and asserts it truncates to 100KB.

## Substep 3: Test Coverage for Cost-Based Routing
- **Problem:** The Server `/tasks/claim` endpoint implements cost-based routing, preventing expensive workers from claiming tasks when cheaper qualified workers are available. However, this logic was completely untested.
- **Fix:** Added `test_cost_routing` to `tests/test_p3_server_idempotency.py`.
- **Evidence:** The test verifies that a worker with `"cost_class": "high"` receives `{"task": None}` when a worker with `"cost_class": "low"` is available for the same target capability, and that the LOW worker correctly claims it.
