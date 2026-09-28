# Specialist Report B — RUN_1 Failure Semantics Review

**Role**: `RUN_1_FAILURE_SEMANTICS`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  

---

```text
FAIL_CONDITIONS=
1. Step A executes more than once (attempts > 1).
2. Result A accepted despite missing or tampered artifact bytes.
3. Verifier issues PASS based on worker-supplied expected_sha256 instead of task-owned expectation.
4. Step B dispatched or executed before Step A has achieved status RECONCILED.
5. Verifier crashes on malformed task (poison pill unhandled exception).
6. HUMAN_RELAY_COUNT > 0 (any manual intervention to forward data, tokens, or state).
7. Any HTTP 500 internal server error or uncaught traceback during execution.

RETRY_BOUNDARY=
- ALLOWED PRE-FLIGHT RETRIES (Before RUN_1 Starts):
  * Ephemeral port binding collision (retry with alternate test port).
  * Temporary file lock on clean staging scratch directory before process launch.
  * Local daemon socket connection timeout during initialization.
- FORBIDDEN RETRIES (During RUN_1 Execution):
  * NEVER retry a failed artifact verification into a pass.
  * NEVER retry an out-of-order Step B dispatch.
  * NEVER restart the coordinator to clear a poisoned state error without recording failure.
  * Any execution failure during RUN_1 immediately invalidates the run (RUN_1 = FAIL).

REQUIRED_FAILURE_EVIDENCE=
1. Full stderr and stdout logs of coordinator, worker daemon, and verifier.
2. Snapshot of central_state.json at the exact moment of failure.
3. Raw JSON payload received at failing endpoint.
4. SHA-256 hash of expected vs actual artifact bytes.
5. Exit code and process table snapshot.

CENTRAL_WRITER_BLOCKER_FORMAT=
FILE: <relative_path>
FUNCTION: <function_name>
DEFECT: <precise_description>
REQUIRED_BEHAVIOR: <unambiguous_fix_requirement>
TARGETED_TEST: <exact_pytest_node>
EVIDENCE: <failing_line_and_traceback>
DO_NOT_CHANGE: <invariants_to_preserve>
```
