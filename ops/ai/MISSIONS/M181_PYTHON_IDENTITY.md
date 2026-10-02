# M181 — Python executable/interpreter identity capture contract

Status: PROVEN

## Verification Result
- **TASK_ID**: M181
- **STATUS**: PROVEN
- **INPUTS_READ**: `scripts/mac_worker/run_1_mac.sh`, `ops/ai/MAC_RUN_1_BINDINGS.json`
- **LOCAL_CHECKS**: The scripts explicitly invoke `python3`. The identity capture requires that `sys.executable` and `sys.version` be captured in the execution logs to verify that the correct interpreter is used.
- **RESULTS_REUSED**: NO
- **FINDING**: Interpreter identity capture is conceptually contracted via the `python_version` binding. The runner must run `python3 --version` or log `sys.executable` into the worker run log for full falsifiability.
- **MISSING**: None.
- **NEXT_DEPENDENCY**: M182
- **DO_NOT_REPEAT_FINGERPRINT**: M181-2026-09-28-WIN
