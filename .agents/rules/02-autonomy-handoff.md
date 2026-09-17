# Courier Autonomy Handoff Rule

When a session reaches a proven terminal state (i.e., CLEAN_IDLE=YES or no executable action remains in the owned scope):

1. Persist the exact final state, evidence, and `NEXT_EXECUTABLE_ACTION` to a durable Ledger/Checkpoint.
2. Set `NEXT_EXECUTABLE_ACTION=NONE` and `WORKER_STATE=IDLE/YIELDED` in the Ledger.
3. Leave the canonical OS-owned persistent services (e.g., Windows Central Motor/server/verifier) running untouched.
4. Terminate/yield the interactive agent session cleanly. Do not ask the user for confirmation, next steps, or emit conversational continuations (e.g., "what next?", "let me know").
5. A completed worker session is disposable; only the durable runtime and Ledger are permanent.
6. If unrelated READY work exists, only continue if it is within your declared ownership/collision scope. Otherwise, yield immediately.
