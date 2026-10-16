# Courier Symphony V1 — Window Custody and Session Lifecycle Protocol

Status: **AUTHORITATIVE DEVELOPMENT-SESSION SAFETY PROTOCOL**

Purpose: prevent loss of real work when Muse/Claude/Antigravity windows are
compacted, cleared, closed, restarted, or repurposed.

This is development orchestration only. Customers never see or operate this
machinery.

Read with:
- `docs/V1_RULE_0.md`
- `docs/V1_PRODUCT_QUALITY_BAR.md`
- `docs/NEXT_CHAT_HANDOFF.md`
- GitHub Issue #54
- `docs/v1/INTEGRATION_LOG.md`

## 1. Core rule

**No window may be cleared, closed, or repurposed until its custody state is known.**

A window is one of:

- `ACTIVE_WRITER`
- `ACTIVE_WORKFLOW`
- `ACTIVE_SCOUT`
- `PARKED`
- `RESOURCE_PAUSE`
- `SAFE_TO_CLEAR`
- `SAFE_TO_CLOSE`

Unknown state is treated as active until proven otherwise.

## 2. Never clear/close when any of these are true

Do **not** clear/close a window if it has:

- an active workflow;
- an active writer task;
- uncommitted writer-owned changes;
- unpushed writer commits that are not durably recorded;
- a live child process/server/test/build it owns;
- a result/checkpoint that exists only in transient scrollback;
- an unfinished phase whose exact continuation has not been checkpointed;
- unresolved ownership/collision state;
- a resource incident whose owned processes are not yet accounted for.

## 3. Required custody check before /clear or close

Before clearing or closing, the window must produce a custody capsule containing:

```
WINDOW_NAME:
ROLE:
CURRENT_HEAD:
STATE:
ACTIVE_WORKFLOW: YES/NO/UNKNOWN
ACTIVE_PROCESS_OWNED_BY_WINDOW: YES/NO/UNKNOWN
UNCOMMITTED_CHANGES: YES/NO/UNKNOWN
UNPUSHED_COMMITS: YES/NO/UNKNOWN
CHECKPOINT_PATH:
DURABLE_HANDOFF: YES/NO
UNFINISHED_PHASE:
NEXT_EXACT_TASK:
SAFE_TO_CLEAR: YES/NO
SAFE_TO_CLOSE: YES/NO
REASON:
```

If any field is `UNKNOWN`, the default is:
`SAFE_TO_CLEAR: NO`, `SAFE_TO_CLOSE: NO`.

## 4. Durability rule

A `/tmp` checkpoint is useful for same-host continuation but is **not** the final
durable record.

Before a window with meaningful unique findings is permanently closed, its
important state must be transferred to at least one durable source:

- the owned writer branch/commit;
- `docs/v1/INTEGRATION_LOG.md`;
- an L1-owned tracked handoff;
- GitHub Issue #54 continuity comment;
- another explicitly designated durable GitHub record.

Read-only scout windows do not gain writer authority merely to save a report.
They write local checkpoints; an orchestrator/harvester promotes only useful,
deduplicated findings into the durable record.

## 5. /compact vs /clear vs close

### /compact

Use during active work when context is large.

Requirements:
- checkpoint first if the current phase is substantial;
- continue same role and ownership afterwards.

### /clear

Use only at a clean phase boundary when:
- custody capsule says `SAFE_TO_CLEAR: YES`;
- checkpoint/handoff is durable enough to resume;
- no active workflow/process depends on the session.

After `/clear`:
1. verify current repo HEAD;
2. read canonical V1 docs;
3. read the saved checkpoint/handoff;
4. resume the exact unfinished task or accept the new assigned role.

### Close window

Use only when:
- `SAFE_TO_CLOSE: YES`;
- no owned process/workflow remains;
- all unique work is durable;
- the window is no longer required for a live workflow.

Closing a terminal that owns a running workflow/process is not cleanup.

## 6. Active workflow rule

A window with a running Muse workflow is `ACTIVE_WORKFLOW`.

Do not:
- `/clear`;
- close the owning Muse process;
- repurpose the window;
- submit duplicate copies of the same factory prompt.

Monitor only with bounded status checks such as `/workflows`.
Do not poll continuously.

When the workflow completes:
- collect its final artifacts;
- deduplicate findings;
- promote actionable results to the correct L1-L6 owner;
- then run the custody check.

## 7. Resource-pressure rule

If any window reports:
- `Too many open files`;
- `EMFILE`;
- `os error 24`;
- repeated shell/tool spawn failures;
- obvious host pressure;

then:
- stop opening new Mac helper processes;
- start no subagents;
- start no new heavy workflow on that host;
- preserve current work;
- account for owned processes;
- mark affected windows `RESOURCE_PAUSE`;
- close only windows proven `SAFE_TO_CLOSE`.

Do not retry-storm.

A failed probe is not evidence that the host is healthy.

## 8. Reuse old windows intelligently

Old windows are not automatically useless and are not automatically safe.

For each old window:
1. run the custody check;
2. if unique unfinished work exists, preserve/resume it;
3. if completed but valuable, harvest it;
4. if stale/duplicate and safe, clear or close it;
5. only then assign a new role.

Never paste a new role over unknown old work.

## 9. Parallelism policy

Aggressive work should come from **deep queued work**, not uncontrolled GUI/session
count.

Mac:
- prioritize a small number of long-running workflows;
- keep additional windows read-only/light;
- under any EMFILE/resource evidence, reduce active windows rather than adding more.

Windows/CI:
- use for Windows-specific execution/build/acceptance;
- still keep writer ownership to L1-L6 only.

Many logical tasks may be queued; only bounded child/process concurrency should be
live at once.

## 10. Orchestrator responsibility

The orchestrator must maintain a current window roster:

```
WINDOW
HOST
ROLE
STATE
OWNER_LANE
CHECKPOINT
DURABLE
NEXT_TASK
SAFE_TO_CLEAR
SAFE_TO_CLOSE
```

Before sleep / long unattended period:
- identify every active writer/workflow;
- identify every stale/legacy window;
- ensure all long-running queues have bounded concurrency;
- park/close proven-unused windows;
- record the roster durably if it materially affects continuation.

After waking:
- read workflow/worker results;
- update the roster;
- harvest useful findings;
- clear/close completed windows only after custody checks;
- activate the next lane based on CURRENT repo evidence.

## 11. Current V1 priority remains unchanged

This protocol does not create new writer lanes.

Locked route:

**ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY**

Only:
- L1 Integration / CI / Golden Harness
- L2 Journal / Controller / API
- L3 Bounded Worker Host
- L4 Verifier / Synthetic Adapter
- L5 Desktop Hub / Replay
- L6 Packaging / Launcher / Paths / Logging / Diagnostics

may be implementation writer lanes.

## 12. Minimal custody prompt

Paste this into any old/unknown window before clearing or closing it:

```
COURIER WINDOW CUSTODY CHECK

Do not start new work.

Inspect only enough current session/repo state to answer truthfully.

Return exactly:

WINDOW_NAME:
ROLE:
CURRENT_HEAD:
STATE: ACTIVE_WRITER|ACTIVE_WORKFLOW|ACTIVE_SCOUT|PARKED|RESOURCE_PAUSE|SAFE_TO_CLEAR|SAFE_TO_CLOSE
ACTIVE_WORKFLOW: YES|NO|UNKNOWN
ACTIVE_PROCESS_OWNED_BY_WINDOW: YES|NO|UNKNOWN
UNCOMMITTED_CHANGES: YES|NO|UNKNOWN
UNPUSHED_COMMITS: YES|NO|UNKNOWN
CHECKPOINT_PATH:
DURABLE_HANDOFF: YES|NO
UNFINISHED_PHASE:
NEXT_EXACT_TASK:
SAFE_TO_CLEAR: YES|NO
SAFE_TO_CLOSE: YES|NO
REASON:

If unique unfinished findings would be lost, write/update the local checkpoint first.

Do not run broad tests.
Do not spawn helpers.
Do not modify product source.
Do not clear yourself.
Do not close yourself.
```

---

**Custody invariant: checkpoint first, durability second, clear/close third. Never
destroy unknown work to make the desktop look tidy.**
