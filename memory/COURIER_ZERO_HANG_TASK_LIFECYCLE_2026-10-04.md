==================================================
14. ZERO-HANG TASK LIFECYCLE / INVISIBLE SELF-HEALING
==================================================

THIS IS A PRODUCT REQUIREMENT, NOT A DEBUGGING CONVENIENCE.

Courier must make stale, hanging, orphaned and abandoned internal tasks
effectively disappear as an operator problem.

A normal user should never have to understand:

- queued prompts
- stuck subprocesses
- stale terminal jobs
- orphan workers
- provider turns
- leases
- retries
- process trees
- zombie tasks

Desired user reaction:

"Wow — this problem is finally gone."

==================================================
CORE LAW
==================================================

A TASK MAY RUN FOR A LONG TIME.

A TASK MAY NOT BECOME OWNERLESS, UNOBSERVABLE OR PERMANENTLY STUCK.

LONG_RUNNING != HUNG
QUIET != HUNG
NO_SCREEN_CHANGE != HUNG

Determine task health from multiple signals.

==================================================
EVERY ACTIVE TASK MUST HAVE
==================================================

TASK_ID=
WORKKEY=
OWNER_SESSION=
OWNER_HOST=
PID_OR_EXECUTION_ID=
PROCESS_START_IDENTITY=
STARTED_AT=
LAST_HEARTBEAT=
LAST_USEFUL_PROGRESS=
LAST_CHECKPOINT=
EXPECTED_ACTIVITY_CLASS=
CANCEL_STATE=
RECOVERY_STATE=

No anonymous "1 task running" forever.

==================================================
TASK LEASE
==================================================

Every active task has a renewable lease.

The owning executor renews it while healthy.

If the lease expires:

DO NOT instantly kill anything.

First reconcile:

1. Does the owner still exist?
2. Is the exact process/execution identity still alive?
3. Is useful progress still occurring?
4. Is another executor already continuing it?
5. Is a durable checkpoint available?
6. Is the task intentionally long-running?

Then classify:

HEALTHY
LONG_RUNNING_HEALTHY
WAITING_EXTERNAL
WAITING_USER
SUSPECTED_STALL
CONFIRMED_STALL
OWNER_LOST
ORPHANED
RECOVERING
DONE

==================================================
STALL DETECTION
==================================================

Never use one fixed timeout for every task.

Use task-class-aware thresholds.

A long build/test/download may legitimately remain quiet.

Require corroborating evidence before CONFIRMED_STALL, such as:

- missed heartbeats;
- no useful progress;
- owner session gone;
- child process exited;
- provider returned idle unexpectedly;
- execution handle invalid;
- task lease expired;
- no checkpoint movement.

One weak signal = investigate.
Multiple consistent signals = recover.

==================================================
SELF-HEALING PIPELINE
==================================================

When a task is CONFIRMED_STALL / OWNER_LOST / ORPHANED:

FREEZE NEW DUPLICATE EXECUTION
→ CAPTURE LAST DURABLE STATE
→ VERIFY OWNERSHIP
→ ATTEMPT GRACEFUL CANCEL
→ WAIT BOUNDED GRACE PERIOD
→ TERMINATE ONLY PROVEN-OWNED PROCESS TREE IF REQUIRED
→ REAP CHILDREN
→ RELEASE OLD LEASE
→ START OR REUSE EXACTLY ONE SUCCESSOR
→ RESTORE FROM CHECKPOINT
→ VERIFY PROGRESS
→ CONTINUE

Never start two successors.

Never restart from the beginning when a valid checkpoint exists.

==================================================
OWNED PROCESS CLEANUP
==================================================

Never blanket-kill:

python
node
powershell
cmd
muse
antigravity
claude
courier

Termination requires deterministic ownership proof.

After cleanup verify:

OLD_PROCESS_ALIVE=NO
OWNED_CHILDREN_ALIVE=0
FOREIGN_PROCESSES_TOUCHED=0
SUCCESSOR_COUNT<=1

==================================================
NO STALE TASK PILE
==================================================

Internal task records must not accumulate forever.

On:

DONE
FAILED_FINAL
CANCELLED
SUPERSEDED

archive the durable receipt and remove the task from the active set.

After crash/restart:

reconcile every ACTIVE record.

Each becomes exactly one of:

RESUMED
RECOVERED
ARCHIVED_DONE
ARCHIVED_STALE
WAITING_USER

No ghost tasks.

==================================================
QUEUE LAW
==================================================

The UI/provider may never accumulate hundreds of equivalent continuation turns.

For one logical campaign:

ACTIVE_EXECUTION <= 1 per owned workkey
PENDING_EQUIVALENT_WAKE <= 1

100 equivalent wakes:

must become:

1 active execution
+
at most 1 RECHECK_NEEDED marker

not 100 queued tasks.

==================================================
USER EXPERIENCE
==================================================

Do NOT expose raw internal clutter to ordinary users.

Normal user-facing states should remain simple:

WORKING
RECOVERING
NEEDS YOU
DONE

If an internal task stalls:

show RECOVERING only when recovery takes long enough to matter.

If recovery succeeds quickly:
the user should ideally notice nothing.

Do not display:
"PID stale"
"lease expired"
"queued prompts 100"
"orphan process"
"heartbeat missed"

unless Developer/Diagnostics mode is explicitly opened.

==================================================
TERMINAL / WINDOW HYGIENE
==================================================

A completed or recovered task must not leave useless terminals,
windows or child processes behind.

Internal workers should prefer headless execution.

Visible windows are an exception, not the execution model.

Courier must not make the desktop progressively messier as work continues.

==================================================
RESOURCE PROTECTION
==================================================

Detect accumulation before the PC becomes unstable:

ACTIVE_TASK_COUNT
OWNED_PROCESS_COUNT
OPEN_HANDLES
VISIBLE_SURFACES
RAM_PRESSURE
QUEUE_DEPTH
ORPHAN_COUNT

Apply backpressure BEFORE resource exhaustion.

Do not create another task merely because capacity exists.

==================================================
RECOVERY RECEIPT
==================================================

For every automatic recovery persist:

INCIDENT_ID=
TASK_ID=
WORKKEY=
OLD_OWNER=
FAILURE_CLASS=
LAST_GOOD_CHECKPOINT=
CLEANUP_ACTION=
SUCCESSOR=
FOREIGN_PROCESS_TOUCHED=NO
DUPLICATE_EXECUTION=NO
WORK_PRESERVED=YES|NO
CONTINUATION_VERIFIED=YES|NO

==================================================
ACCEPTANCE TESTS
==================================================

Add deterministic tests proving:

1. hung owned subprocess is detected and recovered;
2. legitimately long-running quiet task is NOT falsely killed;
3. dead owner + live owned child is reconciled safely;
4. PID reuse fails ownership validation;
5. one stalled task produces exactly one successor;
6. repeated recovery signals do not create duplicate successors;
7. restart leaves zero ghost ACTIVE tasks;
8. completed task leaves zero owned child processes;
9. 100 equivalent continuation wakes produce bounded state;
10. foreign processes are never terminated;
11. stale terminal/surface is reclaimed only after work is durable;
12. one hanging task does not block independent tasks;
13. resource pressure applies backpressure before process/window storm;
14. user-facing state returns from RECOVERING to WORKING/DONE automatically;
15. ordinary UI never requires the user to manually clean internal tasks.

==================================================
PRODUCT ACCEPTANCE
==================================================

The test is NOT merely:

"the daemon recovered."

The real acceptance criterion is:

A user can run Courier for hours/days,
providers can stop,
tasks can hang,
terminals can fail,
sessions can rotate,

and the user's computer does NOT gradually become filled with:

stale tasks
dead terminals
duplicate workers
queued prompts
orphan processes
manual cleanup work.

COURIER CLEANS UP AFTER ITSELF.

THE USER IS NOT THE PROCESS MANAGER.
THE USER IS NOT THE WATCHDOG.
THE USER IS NOT THE CONTINUE BUTTON.
