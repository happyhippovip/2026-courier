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

## Truth and capability

Use this evidence order: current physical runtime > reproducible executable proof > canonical persisted state > current integrated code at exact SHA > current repository/Issue state > documentation > model analysis > old chat > assumption.

Classify important claims as OBSERVED, INFERRED, or UNKNOWN. Never present INFERRED as OBSERVED, and never silently convert UNKNOWN to true/false.

Capabilities are session-local. A listed tool/connector is not proven resource access. Prove repository/runtime access with a successful current read before making current-state claims. Never inherit another model/session's claimed access.

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

Temporary provider wait, temporary idle, queue empty while the goal remains runnable, one completed gate, one completed repair, one passing test, or `PLANNING_EXHAUSTED` are NOT successful stop conditions. If planning is exhausted, use another authorized automatic strategy if one remains; otherwise persist the blocker and escalate `HUMAN_REQUIRED`.

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

## CLEAN_IDLE invariant

`CLEAN_IDLE` is a successful terminal state, not merely an empty queue. It requires a terminal successfully reconciled canonical Goal, no executable or waiting Goal work, no required replenishment, and no unresolved blocker.

`CLEAN_IDLE=YES` is forbidden while any relevant state is `READY`, `DISPATCHED`, `RUNNING`, `WAITING_PROVIDER`, `RETRYABLE`, `REPLENISHMENT_REQUIRED`, `PLANNING_EXHAUSTED`, `BLOCKED`, or `HUMAN_REQUIRED`.

Runtime acceptance must derive CLEAN_IDLE from canonical Goal state plus canonical work state. Empty queue alone never proves CLEAN_IDLE.

## Single truth authority

`SECOND_TRUTH_STORE=NO` means one authoritative source of runtime truth, not one physical copy of data. Local caches, worker state, planner state, chat state, provider state, and generated snapshots may exist but may not override canonical Goal/Task/Execution truth. An intentionally stale non-canonical copy must not be able to cause authoritative dispatch, completion, acceptance, or CLEAN_IDLE.

## Exact process ownership

Every Courier-started temporary task process must have ownership that is durable or unambiguously reconstructable from at least `execution_id`/execution reference, `task_id`, `worker_id`, and process identity. Cleanup may act only on proven Courier-owned processes. Never broad-kill Python/Node/PowerShell/shell processes. Terminal acceptance requires `TEMP_TASK_PROCESSES_AFTER_DONE=0` to be machine-checkable.

## Proof relationship

Targeted failure-injection tests and the continuous physical acceptance run are both required. Neither replaces the other.

Targeted failure injection must cover at least: before dispatch; after dispatch before work; during work; before external effect; after external effect before checkpoint; after terminal result before reconcile; after reconcile before next dispatch. Recovery must preserve work/state and prevent duplicate external effects.

The continuous physical acceptance run must use one canonical Goal, one continuous canonical state history, one OS-owned Motor authority, real workers, and no `USER_CONTINUE`. It must include interruption/resume and at least one external-effect crash boundary.

## Verifier hypothesis to inspect, not assume

Do not assume verifier independence merely from role names. During implementation inspection, determine who creates or changes task-specific proof requirements, whether Planner/Worker can weaken their own acceptance, and whether Verifier can independently reject such movement. Treat this as a hypothesis until current code/runtime evidence proves a defect.

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
- Freeze Goal acceptance criteria, counter definitions, required invariants, tested SHA/version, and proof protocol at the start of a physical acceptance run. A code/spec/protocol change invalidates that run and requires a new run.

## Spec freeze

The specification is sufficient for implementation inspection. Do not expand it for theoretical concerns alone. Add/modify a rule only when current executable evidence shows a concrete relevant failure mode, existing coverage is absent, and a falsifiable proof exists. A real uncovered bug may minimally unfreeze the spec; patch it, freeze again, and return immediately to execution.

## Current product target

The finish path is the current release candidate, not stale PR #35/#38 conclusions. Use CURRENT GitHub state first.

Final proof must come from the real runtime and real workers: one real non-mock goal, OS-owned runtime, interactive agent may exit, automatic result -> verifier -> reconcile -> READY -> next dispatch/replenish, >=10 acceptance-eligible completed tasks, >=2 real workers, `USER_CONTINUE_MESSAGES=0`, no manual process restart/context reconstruction, zero duplicate external effects, zero leaked task-owned processes, then genuine DONE -> CLEAN_IDLE.

Until a valid stop condition occurs: KEEP WORKING.
