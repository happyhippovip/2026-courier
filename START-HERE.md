# START HERE

This is the canonical entry point for Antigravity (Google) continuous execution sessions.

## Quota Recovery Instructions

When starting a new session or recovering from a quota drop:
1. Read `events/runtime-state/CONTINUATION_STATE.json` to recover context.
2. Resume the `CURRENT_TASK` or select `NEXT_SAFE_TASK` if the current task is completed.
3. Execute the task, test, verify evidence, checkpoint, and continue to the next task.
4. **DO NOT** ask the human what to do. **DO NOT** stop unless blocked or forced by the environment.

## Contract
* **MAC Role:** Controller / Dispatcher / External Auditor. Mac receives/derives tasks, submits to Windows via SCP, polls for results, verifies, and updates state.
* **WINDOWS Role:** Persistent Execution Node. Windows autonomously monitors its inbox, executes tasks, and publishes results.
