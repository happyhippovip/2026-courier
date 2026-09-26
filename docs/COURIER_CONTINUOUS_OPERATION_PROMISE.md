# COURIER — Continuous Operation Promise

**Rule #1:** **CONTINUE BY DEFAULT.**

**Slogan:** **Du bist im Urlaub. Courier arbeitet weiter.**

**Operating phrase:** **UNENDLICH — solange Arbeit sicher, erlaubt und technisch möglich ist.**

## What this means

Courier is designed so that the human does not have to refill agent windows, copy results between workers, or restart a mission after ordinary worker completion.

The normal control loop is:

`GOAL -> BACKLOG -> CLAIM -> ADMIT -> WORK -> RESULT_READY -> VERIFY -> CLOSE -> NEXT`

A worker finishing is **not** a reason to stop. A terminal returning to a prompt is **not** a reason to stop. A model session ending is **not** a reason to stop. A host reboot is **not** a reason to lose the mission.

The scheduler/replenisher should keep durable work available and hand the next compatible task to an eligible worker automatically.

## Legitimate pause boundaries

Courier may pause instead of continuing when any of these are true:

- Human Gate: login, OAuth, 2FA, CAPTCHA, purchase/spend, publication/deployment/outreach, admin/sudo/UAC, wallet signing, KYC/legal, or another explicitly human-only action.
- Provider Gate: quota/rate limit, provider outage, unavailable model capacity, or authentication that requires a human.
- Safety/Resource Gate: insufficient or unknown resource state for new heavy work, protected-scope conflict, unsafe process ownership, corrupt control state, or another fail-closed condition.
- Execution Uncertainty: an effect may already have happened but cannot be proven. Preserve state; do not blind-retry.
- Goal Complete: the acceptance evidence for the durable goal is actually satisfied.

A pause must be durable. When the boundary clears, resume the same mission/identity chain rather than silently starting a duplicate execution.

## Product invariant

The target user experience is:

`ONE HUMAN START -> HOURS/DAYS OF VERIFIED CONTINUATION -> HUMAN ONLY FOR REAL GATES`

The system should optimize toward:

- `HUMAN_RELAYS_PER_GOAL -> 0`
- `PREMATURE_IDLE -> 0`
- `DUPLICATE_SIDE_EFFECTS -> 0`
- `LOST_RESULTS -> 0`
- `SAFE_AUTONOMOUS_CONTINUATION -> maximize`

## 64-worker interpretation

`64 workers` means **64 logical worker slots**, not 64 mandatory heavy model processes.

The control plane may keep a large backlog (100/1000+ tasks) while admitting only resource-safe work. Idle logical slots should be cheap. New model processes should be started only when a real task is admitted.

## Provider exhaustion

If Muse, Google, or another provider reaches quota:

1. Persist current task/result/checkpoint.
2. Mark the slot/provider `RATE_LIMITED`.
3. Do not spam retries.
4. Do not rotate accounts to evade provider limits.
5. Continue compatible work through other eligible capacity when available.
6. When the provider becomes eligible again, return the slot to `READY` and continue from durable state.

## Vacation Mode acceptance

Before calling continuous operation proven, demonstrate:

1. Human starts Courier once.
2. Courier dispatches Task A.
3. Worker executes and persists Result A.
4. Courier independently verifies/closes A.
5. Courier dispatches Task B without human relay.
6. Worker/session completion does not strand the queue.
7. Restart preserves the same identity chain.
8. Rate-limit state parks work safely and later resumes.
9. No second conflicting writer is dispatched.
10. A multi-hour bounded soak shows repeated `RESULT -> NEXT` transitions without manual prompt refill.

This is the operational meaning of **UNENDLICH**: not literal infinite compute, but a system that keeps going by default and asks for the human only when the world actually requires the human.
