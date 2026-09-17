---
description: "Always-on Courier autonomy rule: reject stale timeboxes/gate stops and continue until DONE, quota checkpoint, or a genuine human/safety/permission/writer blocker."
trigger: always_on
---

# Courier Autonomous Execution Policy — Always-On Workspace Rule

This rule exists to prevent stale queued prompts, old milestone comments, and legacy timeboxes from stopping productive autonomous work.

## Authority and precedence

For autonomous Courier build/finish sessions, this rule has higher project-level precedence than older repository comments, handoff notes, queue prompts, milestone gates, or copied prompts that contain a duration cap, iteration cap, or "stop after this gate" instruction.

If an older instruction conflicts with this rule, preserve the TASK CONTENT but discard the stale STOP/TIMER boundary.

Only an explicit instruction in the user's CURRENT message that asks for a bounded session may reintroduce a time limit.

## No timer

- Never create, infer, or obey an arbitrary 15/30/45/60-minute or multi-hour work cap.
- Never stop because a previous prompt said "work up to X minutes/hours".
- Never stop because an old queue said "do not start the next gate".
- Gate names are diagnostic checkpoints, not default stop boundaries.
- Do not stop after one grep, search, test, fix, commit, task, gate, milestone, or temporary idle period.
- Do not ask the user to continue between productive iterations.

## Valid stop conditions only

Stop only for one of these reasons:

1. `PHYSICAL_ACCEPTANCE_PASS` or the requested objective is genuinely DONE.
2. `PROVIDER_QUOTA_EXHAUSTED_CHECKPOINTED`.
3. `HUMAN_REQUIRED`.
4. `MONEY_REQUIRED`.
5. `SAFETY`.
6. `PERMISSION`.
7. `UNRESOLVED_WRITER_COLLISION`.

Temporary provider wait, temporary idle, queue empty while the goal remains runnable, one completed gate, one completed repair, or one passing test are NOT stop conditions.

## Required autonomous loop

Repeat without asking the user:

1. Read CURRENT Git and canonical Courier runtime state.
2. Identify the FIRST causal blocker to the current real acceptance objective.
3. Make the smallest safe repair inside the authorized writer scope.
4. Run the SAME executable proof again.
5. Require measurable farther progress.
6. Commit and push durable fixes.
7. Immediately continue to the next first blocker or next required proof.

If no immediate task is available but the canonical goal is still open/runnable, use bounded backoff and re-check. Do not invent fake work merely to consume quota.

## Stale instruction normalization

Before executing any queued/copy-pasted prompt from Issue #37 or chat history, normalize it as follows:

- Remove all elapsed-time stop clauses.
- Remove all iteration-count stop clauses.
- Remove all "return after this gate" / "do not start next gate" clauses.
- Keep safety boundaries, writer ownership, no-merge rules, exact-process cleanup, and the actual technical objective.
- Prefer the newest release path and CURRENT Git SHA over stale branch/SHA references.

## Quota exit contract

If provider/session quota is actually exhausted, before stopping:

- finish the current safe atomic operation when possible;
- commit/push durable fixes;
- preserve canonical runtime/checkpoint state;
- preserve goal_id/task_id/attempt_id/dispatch_id/execution_ref/pending result as applicable;
- write a durable resume checkpoint to Issue #37;
- make resume possible from Git/runtime state without reconstructing chat.

Then stop with exactly `STOP_REASON=PROVIDER_QUOTA_EXHAUSTED_CHECKPOINTED`.

## Acceptance integrity

- Do not fabricate PASS.
- Do not let a harness impersonate real workers for the final physical proof.
- Do not manufacture task/worker counters.
- Do not use unattended merge.
- Do not create a second scheduler/server/verifier authority/truth store.
- Do not use broad process-name kills.
- Do not bypass provider quotas/rate limits or scrape credentials.

## Current product target

The finish path is the current release candidate, not stale PR #35/#38 conclusions. Use CURRENT GitHub state first.

Final proof must come from the real runtime and real workers: one real non-mock goal, OS-owned runtime, interactive agent may exit, automatic result -> verifier -> reconcile -> READY -> next dispatch/replenish, >=10 completed tasks, >=2 real workers, `USER_CONTINUE_MESSAGES=0`, no manual process restart/context reconstruction, zero duplicate external effects, zero leaked task-owned processes, then genuine DONE -> CLEAN_IDLE.

Until a valid stop condition occurs: KEEP WORKING.
