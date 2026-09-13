# Symphony Durable Autonomy Bootstrap

If you are a fresh Antigravity agent or have lost your chat history context, this file serves as your canonical entry point for safely resuming autonomous operations without requiring the human to type `weiter`.

## 1. Discover Durable State
Read the current branch, Git status, and the JSON state file:
`.courier_state/mac_autonomy_state.json`

## 2. Reconcile
Do not blindly trust prose or historical summaries. Reconcile the state file against:
- Running `ps` / `launchctl` processes
- `.courier_state/motor.db` SQLite tasks and leases
- Git working tree state

## 3. Verify Last Result
If `mac_autonomy_state.json` indicates a recently finished task, use `ResultCustoms` or independent scripts to verify that its expected effect was achieved. Add it to `DO_NOT_REPEAT` if successful.

## 4. Gap Discovery & Safety Check
Before proceeding, you MUST verify:
- No ACTIVE_WRITER is conflicting with your lane.
- No branch-local HUMAN_GATES are blocking progress.
- The next task is NOT in `DO_NOT_REPEAT`.

## 5. Execution Loop
Discover the next highest-value safe gap. Update `NEXT_SAFE_TASK` and `CONTINUATION_DECISION: CONTINUE` in the state JSON. Do your work, verify it, create a checkpoint, and then end your turn. 

If no safe gaps remain, or a human gate blocks you, set `NEXT_SAFE_TASK: null` and `CONTINUATION_DECISION: STOP`, then gracefully end your turn. The Antigravity Stop Hook will enforce true idle.
