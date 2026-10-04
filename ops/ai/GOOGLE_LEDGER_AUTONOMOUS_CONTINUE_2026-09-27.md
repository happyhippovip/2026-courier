# Google Ledger Autonomous Continue Prompt — 2026-09-27

Use the MASTER once in the isolated Mac Google writer window. Then use the short CONTINUE prompt repeatedly only while the worker reports a unique next task.

## MASTER

```text
ROLE=GOOGLE_LEDGER_AUTONOMOUS_WRITER
HOST=MAC
MODE=ISOLATED_PARALLEL_LEDGER_LANE

OBJECTIVE:
Turn Courier's existing ledger/evidence work into a production-usable foundation for:
- internal verified execution history
- owner observability
- future Muse wall usage
- future customer-facing ledger included with Courier
- future complaint / credit / refund evidence workflows
while never disturbing the Windows final-candidate writer.

WINDOWS FINAL-CANDIDATE WRITER OWNS THESE FILES:
1 scripts/courier_verifier.py
2 scripts/integration_contract.py
3 tests/test_artifact_upload_flow.py
4 server/app.py
5 tests/test_p3_server_idempotency.py

NEVER EDIT THEM.
NEVER SWITCH OR MODIFY THE WINDOWS WRITER BRANCH/WORKTREE.

Use only your isolated Mac worktree/branch.
Prefer new non-conflicting modules/tests/docs/fixtures.

CORE RULE:
EXTEND EXISTING LEDGER/EVIDENCE DESIGN.
DO NOT CREATE A SECOND SCHEDULER, SECOND QUEUE, SECOND VERIFIER OR SECOND CONTROL PLANE.

==================================================
AUTONOMOUS QUEUE
==================================================

Maintain one durable queue in your isolated branch:

ops/ai/LEDGER_AUTONOMOUS_QUEUE_2026-09-27.json

Each queue item must contain:

task_id
title
gate
write_scope
forbidden_scope
dependency
acceptance_evidence
status
result_commit
notes

Allowed status:
QUEUED
ACTIVE
DONE
BLOCKED
OBSOLETE

At the start of every iteration:

1. read the queue
2. mark any already-proven duplicate task OBSOLETE
3. select exactly ONE highest-priority QUEUED task whose dependencies are met
4. mark it ACTIVE
5. complete only that task
6. run focused tests
7. commit only its bounded changes
8. record evidence + commit SHA
9. mark it DONE
10. choose the next unique task

If no unique ready task exists:
return:
LEDGER_QUEUE_IDLE_SAFE=YES
and STOP.

Never invent busywork just to consume prompts.

==================================================
INITIAL WORKSTREAMS
==================================================

A. EXISTING_LEDGER_INVENTORY
Find and document existing ledger/evidence primitives.
Do not duplicate them.

B. APPEND_ONLY_EVENT_CORE
Provide/extend a lightweight append-only event representation with:
schema/version
event identity
timestamp
goal/task/attempt/dispatch/result references where applicable
event type
previous state
next state
reason
evidence references
restart-safe persistence
malformed-record rejection

C. LEDGER_READ_MODEL
Read/filter by:
goal
task
attempt
dispatch
result
event type
time/order
without mutating history.

D. LEDGER_INTEGRITY
Use the simplest integrity mechanism consistent with the repo.
No cryptographic theater.
Historical records must not silently change.

E. OWNER_OBSERVABILITY_SUPPORT
Make it possible for a later read-only UI to answer:
what happened
when
why
which attempt
which dispatch
which result
reported vs verified
retry/replay
recovery
human-required

Do NOT build the UI.

F. MUSE_WALL_LEDGER_SUPPORT
Prepare a bounded interface/fixture so future Muse wall workers can:
append/read evidence through approved ledger APIs
attach their task/result references
resume after restart
without becoming a scheduler authority.

Do NOT spawn a wall today unless explicitly authorized.

G. CUSTOMER_LEDGER_MODEL
Prepare customer-safe event types and projections for future product use.

Customer-facing ledger must eventually support:
service/task reference
proof reference
billing/payment-provider reference
entitlement/credit reference
complaint/support case
refund/credit status
resolution reason
exportable privacy-filtered history

Do not store:
raw card details
bank credentials
API keys
provider secrets
raw payment payloads unless explicitly necessary and redacted.

H. COMPLAINT_REFUND_EVIDENCE_MODEL
Prepare event/state primitives for:

CUSTOMER_REQUESTED_REVIEW
SUPPORT_CASE_OPENED
EVIDENCE_ATTACHED
DECISION_PENDING
APPROVED_REFUND
APPROVED_CREDIT
DENIED_WITH_REASON
PROVIDER_REFUND_SUBMITTED
PROVIDER_CONFIRMED
PROVIDER_FAILED
PROVIDER_PENDING
CUSTOMER_NOTIFIED
CASE_CLOSED

Do NOT implement real payment-provider refunds yet.
Do NOT invent legal refund policy.

The goal is traceability so customers do not lose money silently and support can explain/resolution every case.

I. ENTITLEMENT_SAFETY
Prepare evidence primitives to distinguish:
entitlement granted
entitlement consumed
entitlement restored
unknown/pending

Failed/ambiguous Courier execution must not silently look like consumed customer value.

J. CUSTOMER_EXPORT
Prepare a privacy-safe export/projection contract.
The customer sees only their own relevant records.
No internal prompts/logs/secrets/private worker identifiers.

K. MUSE_TOMORROW_TASKBANK
Create/update:
ops/ai/MUSE_LEDGER_WALL_TASKBANK_2026-09-28.md

Tasks must be independent, bounded, read-mostly or isolated-write tasks.

For each task:
TASK_ID
PURPOSE
DEPENDENCY
WRITE_SCOPE
FORBIDDEN_SCOPE
ACCEPTANCE
STOP_CONDITION

Prioritize tasks Muse can execute tomorrow without rereading the whole repo.

L. COOL_MACHINE_BONUS_TASKS
Prepare optional low-risk tasks for Muse to run only when resource admission says the Mac is cool enough.

These tasks must:
- be bounded
- avoid heavy fan-out
- not spawn many processes
- not touch Windows-owned files
- have a cheap stop condition

Examples:
focused ledger fixtures
schema validation tests
restart-read tests
customer-export redaction tests
documentation/evidence extraction

No hardware stress.
One heavy slot max unless later evidence changes admission.

==================================================
CUSTOMER MONEY SAFETY
==================================================

Courier must never claim money safety from an internal counter alone.

Future paid product must distinguish:
PAYMENT_AUTHORIZED
PAYMENT_CAPTURED
ENTITLEMENT_GRANTED
SERVICE_ATTEMPTED
SERVICE_VERIFIED
REFUND_REQUESTED
REFUND_APPROVED
REFUND_SUBMITTED
REFUND_CONFIRMED
REFUND_FAILED/PENDING

Unknown provider state stays UNKNOWN/PENDING.

Use provider-issued transaction/refund IDs and idempotency keys when later integration exists.

Refund/credit must be new append-only events.
Never silently rewrite the original charge event.

Before real paid launch:
require one dedicated payment/refund readiness review.

==================================================
TEST LAW
==================================================

Every code task requires focused deterministic tests.

Do not run huge broad suites unless the changed component requires it.

Useful ledger tests include:
append preserves history
reload preserves history
malformed records rejected
identity binding enforced
event order preserved
restart does not mutate history
duplicate event behavior explicit
attempts remain distinguishable
dispatch generations remain distinguishable
verification bound to correct result
customer projection redacts private fields
refund/credit event does not mutate original payment event
unknown payment state remains unknown
export cannot cross customer boundary

==================================================
MUSE TOMORROW
==================================================

Muse should be able to use the ledger foundation tomorrow as a wall/tool,
but NOT by taking scheduler authority.

Prepare:
- concise taskbank
- concise API usage note
- fixtures
- focused tests
- restart-safe examples
- one short continuation prompt

Do not require every Muse window to reread the repository.

==================================================
TOKEN / CREDIT RULE
==================================================

We may send the continuation prompt many times.

Therefore every iteration MUST be incremental.

Never repeat:
repo inventory
already-completed tests
already-written docs
already-settled architecture

Use durable queue/checkpoints to resume.

If task is already DONE:
skip it.

If blocked:
record BLOCKED and move to another independent ready item.

If nothing useful remains:
STOP.
Do not manufacture work.

==================================================
EXPENSIVE REVIEWERS
==================================================

Do NOT call Opus or Codex per iteration.

After the autonomous ledger batch is genuinely complete:

CODEX:
exactly 1 final code-grounded ledger review if code/integration is substantial.

OPUS:
exactly 1 product/security/customer-safety convergence review if a real product decision remains.

Do not spend them on repeated summaries.

==================================================
RETURN EACH ITERATION
==================================================

ITERATION_TASK_ID=
TASK_STATUS=DONE/BLOCKED/OBSOLETE
FILES_CHANGED=
TEST_COMMAND=
TEST_RESULT=
COMMIT_SHA=
QUEUE_DONE_COUNT=
QUEUE_BLOCKED_COUNT=
NEXT_UNIQUE_TASK=
WINDOWS_CONFLICT=YES/NO
HEAVY_RESOURCE_REQUIRED=YES/NO
SAFE_TO_CONTINUE=YES/NO

Keep this response compact.

STOP immediately if:
- a required change touches Windows-owned final-candidate files
- integration depends on unfinished final-candidate behavior
- the work creates another scheduler/control plane
- no unique useful task remains
```

## CONTINUE

Use this after the MASTER only while SAFE_TO_CONTINUE=YES:

```text
CONTINUE_LEDGER_AUTONOMY

Resume ONLY from the durable ledger queue/checkpoint.
Do not reread completed work.
Take exactly one next unique ready task.
Respect Windows-owned forbidden files.
Run focused evidence/tests, commit bounded changes, update the queue.
If no unique ready task remains: LEDGER_QUEUE_IDLE_SAFE=YES and STOP.
Return only the compact iteration status from the master prompt.
```

## Repetition rule

Do not blindly force 100 useful iterations.

It is safe to paste the CONTINUE prompt repeatedly because the worker must self-stop when the queue is empty or blocked. The desired outcome is completion, not prompt count.
