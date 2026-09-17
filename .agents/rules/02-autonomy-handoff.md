# Courier Autonomy Handoff Rule

When a session reaches a proven terminal state (i.e., CLEAN_IDLE=YES or no executable action remains in the owned scope):

1. Persist the exact final state, evidence, and `NEXT_EXECUTABLE_ACTION` to a durable Ledger/Checkpoint.
2. Set `NEXT_EXECUTABLE_ACTION=NONE` and `WORKER_STATE=IDLE/YIELDED` in the Ledger.
3. Leave the canonical OS-owned persistent services (e.g., Windows Central Motor/server/verifier) running untouched.
4. Terminate/yield the interactive agent session cleanly. Terminal worker handoff MUST explicitly return scheduling authority to the persistent Motor.
5. A completed worker session is disposable; only the durable runtime and Ledger are permanent. WORKER_STATE=IDLE/YIELDED applies only to the disposable interactive worker/session, NEVER to the persistent Courier Motor.
6. If unrelated READY work exists, only continue if it is within your declared ownership/collision scope. Otherwise, yield immediately.

## Anti-Patterns
- `tail -f`, sleep loops, terminal log-followers, interactive waiting, or keeping an agent session alive merely to observe progress MUST NEVER be used as Courier's autonomy mechanism.
- Logging/observability must be non-blocking and separate from scheduling/control flow.
- No polling implemented by keeping an interactive agent alive.
- No waiting timers used to fake persistence.
- Do not ask the user for confirmation, next steps, or emit conversational continuations (e.g., "what next?", "let me know").

## Regression Invariants
- `INTERACTIVE_AGENT_REQUIRED_FOR_PROGRESS=NO`
- `TAIL_BASED_CONTROL_FLOW=NO`
- `MOTOR_ALIVE_AFTER_AGENT_EXIT=YES`
- `READY_AFTER_AGENT_EXIT_AUTO_DISPATCHES=YES`
- `AGENT_BACKGROUND_TASKS_AFTER_HANDOFF=0`

## Prevention of Antigravity Task Leaks
- An agent session may NOT claim `WORKER_STATE=IDLE/YIELDED`, `CLEAN_IDLE=YES`, or terminal handoff while any background task it created (e.g. via `run_command` with `IsDaemon=true` or similar) remains alive.
- All persistent Antigravity background tasks created for orchestration or monitoring MUST be strictly terminated using `manage_task` (Action="kill") before yielding.
- Replace indefinite monitoring with bounded/nonblocking inspection (e.g. read the last N lines once, check state once). Observation must never remain as a running agent background task.
