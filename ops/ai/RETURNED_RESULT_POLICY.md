# Courier Symphony — Returned Result Policy

Purpose: prevent the human from becoming the normal scheduler when an agent, provider session, or worker returns a result.

## Core rule

**Agent return != request for another human prompt.**

A provider/chat/session ending is not by itself a task failure, a human wall, or permission to invent more work.

For every returned result, CHIEF/Courier must:

1. **Persist** the returned DurableResult/checkpoint/evidence using the existing authoritative state mechanism.
2. **Classify** what the result actually proves: `PROVEN`, `OPEN`, `BLOCKED`, `OBSOLETE`, `CONTRADICTED`, or `NEEDS_VERIFICATION`.
3. **Update acceptance gates** only from current durable evidence. Never carry an old PASS/FAIL/test count onto a newer SHA/runtime without verification.
4. **Infer before querying**: determine what already follows from known durable state, then verify only genuine remaining uncertainty with exact reads/deltas/bounded tests.
5. **Recompute dependency-safe READY work** from already-authorized work. Do not create work merely to keep agents busy.
6. **Check ownership and liveness** before dispatch. Preserve one writer per logical scope and never re-prompt an owner that is already active/progressing.
7. **Dispatch only the smallest existing dependency-safe READY item** to a qualified available worker, using existing Courier routing/idempotency mechanisms.
8. **Continue automatically when safe**; otherwise enter durable `IDLE`, `DONE`, `WAITING/BLOCKED`, or a genuine `HUMAN/MONEY/SAFETY/PERMISSION` wall.

## Scope-exhaustion rule

Completing one subtask is not automatically the end of an authorized run.

Before returning to the human, ask deterministically:

> Does another already-authorized, dependency-safe READY item exist inside an available owner's scope?

- **YES:** continue through the normal Courier result -> verify -> reconcile -> READY -> dispatch path.
- **NO:** persist the terminal/idle/blocker state and stop.
- Never infer/create speculative tasks solely to avoid idleness.

## Anti-duplication

Before any new dispatch or agent prompt:

- identify the logical scope and current owner;
- determine whether a live execution already owns it;
- reuse current durable goal/task/attempt/dispatch identities;
- do not start a duplicate writer or duplicate logical execution;
- do not resend an assignment merely because a chat/session returned or restarted.

## Resource rule

Prefer event/result-driven continuation and existing deterministic Courier mechanisms.

Do not use AI for routine polling, hashing, copying, simple state transitions, or unchanged-test repetition.

Avoid:
- busy loops;
- aggressive retry/heartbeat loops;
- duplicate workers;
- repeated unchanged builds/tests;
- broad repository scans;
- resident AI sessions whose only purpose is waiting;
- unnecessary CPU/RAM/I/O/network use.

Recovery for vanished workers/restarts must be bounded and evidence-based; reuse existing lease/recovery mechanisms where present rather than adding a watchdog/polling architecture by default.

## Current finish order

Until core acceptance is complete, prioritize:

`Ledger trust / authoritative persistence`
-> `remaining causal Ledger/Guard/Motor defects`
-> `DurableResult -> verify -> reconcile -> next READY -> automatic dispatch`
-> `physical zero-human A->B`
-> `session/process/restart recovery`
-> `minimal resource/data/cost finish`
-> `FREEZE core`.

Product/revenue work may preserve hard-to-retrofit interfaces (identity, permissions, secrets boundaries, idempotency, audit/evidence, budget/quota boundaries, provider/worker capability abstraction) but must not interrupt the Ledger/Core critical path.

## Current role discipline

- **Google/Central:** existing production owner for its assigned Ledger/Guard/Motor/Central scope.
- **Codex:** independent reviewer/gap finder unless explicitly assigned an unowned writer scope.
- **Muse:** complementary QA/reproducer/package verification unless explicitly assigned an unowned writer scope.
- **CHIEF/ChatGPT:** coordinator/reconciler; reduce work and select the smallest remaining causal edge, not a competing production writer.

These roles must be revalidated against current durable ownership before acting; this document does not override a newer explicit durable ownership transition.

## Human-return condition

Normal continuation must not require the human to type `continue`, relay prompts, select workers, or reconstruct chat history.

Return to the human only when:
- no dependency-safe authorized work remains; or
- a genuine HUMAN/MONEY/SAFETY/PERMISSION wall exists; or
- destructive ambiguity / unavailable required credentials or target / unresolved ownership collision prevents safe progress.

## Acceptance target

`ONE GOAL -> A -> real Result A -> automatic verify/reconcile -> B READY -> automatic dispatch -> real Result B -> DONE`

Required property:

`HUMAN_CONTINUE_BETWEEN_A_AND_B = 0`

This policy is an operating contract, not proof that the underlying auto-continuation/restart implementation already exists. Physical evidence is still required before declaring that behavior complete.
