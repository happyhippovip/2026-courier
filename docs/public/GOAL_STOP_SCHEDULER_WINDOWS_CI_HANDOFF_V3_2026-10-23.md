# Courier Symphony — Goal Stop, Checkpoint, Scheduler & Windows-CI Handoff V3

> **FORTSETZUNG ALS RELEASE TRAIN V1:** Der bestätigte Windows-CI-Befund aus diesem Checkpoint ist die rote Phase-2-Abnahmefrage in der [fünfstufigen Strategie](./COURIER_RELEASE_TRAIN_STRATEGY_V1_2026-10-23.md). Die [fünf Master-Prompts](./COURIER_RELEASE_TRAIN_PROMPT_PACK_V1_2026-10-23.md) trennen Grok-Koordination, Windows-Fix, unabhängige Abnahme, L1-Merge und Cursor-Produktfortsetzung. **Nicht** erneut als Mac-Worker-CONTINUE ausführen.
**Public coordination checkpoint | 23 October 2026 | documentation only**

> **This is a verified public GitHub knowledge checkpoint**, not a runtime snapshot of a personal Mac/Windows device. Publishing this page does not install a schedule, restart an agent, create a Workkey, grant a Writer-Lease, or make a red test green. Keep private operational data and any secrets in the existing authorized private project-memory repository.

## A. Verified GitHub status (23 October 2026, time-sensitive)

- `integration/v1`: `81bbf224b0aeeca4a2b92db29dfc7220b707043a`, merging [#835](https://github.com/happyhippovip/2026-courier/pull/835). Older green SHA `e9d7f1f29c26` is *historical*, not the current integration HEAD of this checkpoint.
- [Courier v1 CI run 40008119253](https://github.com/happyhippovip/2026-courier/actions/runs/40008119253): **FAILURE**. The **Windows pytest** job failed. Ubuntu pytest, desktop JS, Windows build, and Golden skip ratchet completed successfully.
- [Customer-Reality Gate 40008119364](https://github.com/happyhippovip/2026-courier/actions/runs/40008119364): **SUCCESS** on the same commit. This does **not** override the red Courier v1 CI result.
- Confirmed failing test: `tests/test_windows_worker_contract.py::test_success_without_any_artifact_evidence_is_reported_failed`, runner assertion at line 346.
- Observed: a worker posted `status=FAILED` and `artifacts=[]`, yet the central task stayed `DISPATCHED`; test expected `QUEUED`. Windows pytest reported **1 failed, 3754 passed, 99 skipped, 6 xfailed**, with exit status 1.
- **Cause remains UNPROVEN.** The failure may involve worker, central task state, result/release handling or the expected contract. Do not weaken the test or silently reinterpret `DISPATCHED` as success. Owner handoff to the existing Windows Worker owner first; route any central Controller/Journal changes to its actual L2 owner. Writer-lease is required for edits.
- PR [#836](https://github.com/happyhippovip/2026-courier/pull/836), [#837](https://github.com/happyhippovip/2026-courier/pull/837), [#838](https://github.com/happyhippovip/2026-courier/pull/838), [#839](https://github.com/happyhippovip/2026-courier/pull/839) and [#840](https://github.com/happyhippovip/2026-courier/pull/840) were open at the last check; reverify before citing as current. Independent approval and L1 merge authority remain required.

## B. Meaning of “Goal reached” after ~14 minutes 56 seconds

**GOAL_RUN_COMPLETED** means the current run ended. It is not proof of a continuously active worker, nor proof that a later wake-up will or will not occur. Distinguish these independent states:

| Observed status | Meaning | Next safe action |
| --- | --- | --- |
| Goal run completed; **native timer/watch ACTIVE** | A later wake-up may be scheduled | Reuse the one existing mechanism, confirm exact target and next event once; do not create a duplicate |
| Goal run completed; **timer/watch INACTIVE** | No automatic restart established | Preserve checkpoint and make one explicit, bounded proposal for an available native wake method; do not activate it without required approval |
| Goal run completed; **timer/watch UNKNOWN** | One screenshot/report cannot prove persistent scheduling | Label `RESUME_UNVERIFIED`; examine the correct application's Goal/Tasks/Schedules or Project Listening panel |
| Timer/watch active but unchanged HEAD/CI/workkey/lease | No distinct eligible work | `QUIESCENT_SAFE`, no repeated tests, no subagent, no duplicate wake-up |
| New material CI/PR/owner event with a *distinct authorized scope* | Genuine continuation candidate | Deduplicate by `app|agent|event-id|PR|SHA|workkey|acceptance-question`; perform one permitted unit; save new evidence |
| No Writer-Lease on the relevant Windows worker files | Mac/Cloud verifier cannot edit them | Produce a precise owner handoff, not a workaround or new lease |

**A Goal, a schedule, a subscription, a hook and a canonical Workkey are separate systems.** A public Markdown prompt is instructions, not executable orchestration. The number of minutes a session ran is neither a release criterion nor a reason to create new activity.

## C. Explicit application boundaries

**Google Antigravity Mac** (separate application and session):
- The user's 23 October screenshots *reported* an already active `/goal`, **one 30-minute wake-up**, GitHub event observations, and a deadline around 24 October 2026, 19:56 Europe/Berlin. This is screenshot-/agent-reported, NOT remotely inspected live scheduler state. Verify exact wake target and expiry in that same application.
- Its [existing V2 public prompt](https://github.com/happyhippovip/2026-courier/blob/docs/public-workflow-2026-10-23/docs/public/GOOGLE_MAC_AUTO_RESUME_PROMPT_V2_2026-10-23.md) is managed separately in **PR #839**. This addendum **does not modify** that branch.
- Don't paste Cursor slash commands or Project-specific hooks into Antigravity. No second 30-minute schedule, parallel stop hook, or sidecar.

**Cursor Ultra Mac – Project coordinator**:
- The Coordinator (not a finished worker) owns *supported native project delegation*. Confirm actual Project Listening subscriptions, their event targets, active Cloud Agents, dedupe and included usage before assuming they run.
- Use the [Cursor Project Coordinator V1](./CURSOR_ULTRA_MAC_PROJECT_COORDINATOR_PROMPT_V1_2026-10-23.md), supplemented by this checkpoint. A completed A→B lane without a READY Workkey/Writer-Lease remains `QUIESCENT`.
- Cursor `courier-safe-autonomy` skill in PR #840 is a *proposal* with auto-invocation disabled, not a deployed stop hook. No recursive `stop` reinjection to fill the queue.

**Cursor Ultra Mac – individual Cloud Worker**:
- Executes only an actually claimed/approved distinct Workkey with its current owner/scope. The [Worker V1](./CURSOR_ULTRA_MAC_WORKER_HANDOFF_PROMPT_V1_2026-10-23.md) covers this.
- A Cloud VM does not prove live local Mac access.

**Windows Worker owner**:
- Responsible for investigating the specific Windows state transition and proposing a minimal targeted fix under an actual authorized lease. A Mac verifier or Grok coordinator may pass the evidence; neither may claim the code or merge without scope.

## D. Copy once only when a Goal run has completed (correct application)

```text
👑🥊👊😎🧪⚗️🚀 COURIER — GOAL COMPLETED / SAFE RESUME HANDOFF V3

You finished a bounded Goal run; do not claim continuous background work.
Identify the application and role first: Google Antigravity Mac / Cursor
Project coordinator / assigned Cursor Cloud Worker / Windows Worker.

1. Read the last authorized checkpoint and current verified integration HEAD.
2. Check native Goal/Task/Schedule/Listening status in THIS application.
   Report ACTIVE / INACTIVE / UNKNOWN and the actual next wake-up target.
3. If there is already ONE active timer or event subscription: KEEP it.
   No second timer, loop, schedule, stop hook, sidecar or sender.
4. Treat a new event as actionable only after matching a distinct, approved
   Workkey/scope. Deduplicate event-id + PR + SHA + acceptance question.
5. On unchanged HEAD, CI, Workkey and lease: QUIESCENT_SAFE with no
   tests, new agents, queue refill or repetitive chat message.
6. On a genuine new failure, verify exact CI/run/test, record the
   smallest reproducible counterexample and route to its current owner.
7. At integration/v1 81bbf224, verified Windows CI #40008119253
   failed test_success_without_any_artifact_evidence_is_reported_failed:
   expected QUEUED, observed DISPATCHED. This is a *dated snapshot*;
   check current HEAD and newer CI before creating any work.
8. If no Windows Writer-Lease, do not edit worker/Controller files.
   Send an owner-scoped, nonduplicated handoff.
9. Save HEAD, evidence source, new result, owner, lease state, cost state,
   scheduler state and next permitted event in a durable private checkpoint.
10. No hidden five-day operation claims, no fake zero-cost assertions,
    no PAYG, no merging or production release without authorization.

SINGLE_WRITER=YES; HEAVY_JOB_LIMIT=1; UNKNOWN_COST=BLOCK;
ADDITIONAL_SPEND_EUR=0; NO_UNAUTHORIZED_MERGE=YES;
REAL_TRADES=0; WALLET_SIGNING=NO.

OUTPUT ONCE IF USEFUL:
APPLICATION | GOAL_RUN_STATUS | NATIVE_WAKE_STATUS | NEXT_WAKE |
CURRENT_SHA | CI_GATE | WORKKEY | OWNER | LEASE | CHECKPOINT |
NEXT_REAL_EVENT

When no eligible change: QUIESCENT_SAFE. Do not send CONTINUE.
```

## E. Durable checkpoints versus automated processes

There are **two distinct checkpoint types**:
1. **This public documentation checkpoint**: a GitHub commit documenting verified evidence, ownership, and safe continuation semantics. Its presence can be verified by opening this URL and checking the blob. It does NOT save runtime `authority.db`, local dirty files, private messages, or scheduled app state.
2. **A private operational checkpoint**: a real written and read-back-verified record in the authorized private Courier project-memory/handoff location, containing Workkey/lease/run identity and logs where appropriate. Merely saying "checkpoint written" is a REPORTED claim until its destination is independently checked.

A native subscription may wait for events but does not authorize a writer. A stopped Goal may have an active future timer; an active Goal does not imply a persistent host process. Do not conflate their lifecycles.

## F. Review before integrating public documentation

This file is published on a dedicated documentation branch alongside Cursor Mac prompts. The **Google Antigravity Mac** workflow remains owned by PR #839; this file intentionally references rather than edits it. No workflow YAML, engine code, hooks, schedules, User accounts, external actions or production files are modified.

**Status:** DOCUMENTED / GitHub verified as of 2026-10-23. A repair for the Windows CI failure is NOT claimed here.
