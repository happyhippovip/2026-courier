# Courier Symphony V1 — Product Quality Bar

Status: **AUTHORITATIVE QUALITY / CUSTOMER-EXPERIENCE CONTRACT FOR V1**

This document does **not** redesign the Dennis + ChatGPT + Opus V1 architecture.
It makes the existing route harder to break and defines what "finished" means from
the customer's point of view.

Read together with:
- `docs/V1_RULE_0.md`
- `docs/NEXT_CHAT_HANDOFF.md`
- GitHub Issue #54
- `docs/v1/INTEGRATION_LOG.md`

## 0. Rule 0 still wins

**FINISH THE PRODUCT.**

Locked route:

**ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY**

PC first. Windows 11 first. Phone/mobile comes later and must reuse the same
ledger/controller truth rather than create a second runtime.

## 1. Customer promise: Courier operates the machinery, not the customer

The development experience may contain branches, prompts, model names, CI runs,
`/goal`, `/clear`, internal error codes, or debugging tools.

The shipped Courier experience must not require the customer to understand or
operate any of those things.

A customer must never need to:
- open terminals;
- paste agent prompts;
- choose L1-L6;
- choose model effort;
- understand `YOLO`, `EMFILE`, `fcntl`, GitHub Actions, worktrees, branches,
  subagents, checkpoints, or provider implementation details;
- manually restart a worker because a normal recoverable condition occurred;
- read a stack trace to know whether their work succeeded.

Courier should automatically do safe recovery when the truth is known. It should
ask the user only when a real permission, consequential action, ambiguous
non-idempotent outcome, or human decision is required.

Internal technical detail belongs behind **Details / Diagnostics**, not in the
primary product flow.

Never convert uncertainty into success merely to keep the interface calm.

## 2. "Luxury" means quiet competence

The target feeling is not "AI is busy". It is:

- instant or near-instant feedback to input;
- no fake activity;
- no noisy status churn;
- no unnecessary modal warnings;
- useful local operation even when optional providers are unavailable;
- safe automatic recovery;
- visible, trustworthy completion;
- smooth replay of real work;
- clear next action only when the user actually needs to act;
- low idle CPU, memory churn, wakeups, heat, fan noise, and background network use.

If the user cannot change anything as a result of a warning, prefer a quiet status
or diagnostic entry rather than interrupting them.

## 3. Reliability classes

Courier treats these as different problems.

### A. Truth / correctness failure — HARD BLOCKER

Examples:
- lost event;
- duplicate external effect;
- false PASS;
- stale/late result accepted;
- replay differs from live projection;
- corrupt journal treated as healthy;
- worker still running after Courier claims it stopped.

Response:
- fail closed;
- preserve evidence;
- block unsafe automation;
- never baseline away a new correctness regression.

### B. Recoverable infrastructure failure

Examples:
- transient network failure;
- provider temporarily unavailable;
- database busy;
- worker temporarily unavailable.

Response:
- bounded retry with backoff;
- deterministic idempotency key;
- finite terminal outcome;
- preserve result/outbox state across restart;
- no retry storm.

### C. User-action-required state

Examples:
- permission needed;
- destructive action requires approval;
- non-idempotent effect may have happened but cannot be proven;
- conflict cannot be resolved safely.

Response:
- one clear Human Desk item;
- plain language;
- show exactly what Courier knows;
- no blind retry.

### D. Internal implementation error

Response:
- capture local diagnostics and correlation/event ID;
- keep customer message concise and actionable;
- never expose raw stack traces, branch names, model names or orchestration jargon
  in the normal UI.

## 4. Known failure classes that V1 must explicitly prevent

These are not theoretical. Current/history evidence has already exposed these
classes, so V1 acceptance must contain tests for them.

1. **Process-tree orphan after timeout**
   - A timeout is not complete until the owned parent/child/grandchild tree is
     proven gone.
   - Windows V1 must use exact owned-process containment, preferably Windows Job
     Objects, rather than broad name-based kill heuristics.

2. **Fail-open resource probes**
   - A failed health/resource measurement must not silently mean "healthy".
   - Unknown resource state blocks new heavy work or degrades to a bounded safe
     mode.

3. **Unbounded stdout/stderr or logs**
   - Child output and logs need explicit size/rotation limits.
   - A noisy child must not be able to OOM the worker.

4. **Heartbeat / lease deadline collision**
   - Execution heartbeat cadence and controller lease/reclaim deadlines must have
     deliberate safety margin.
   - A live task must not be quarantined merely because timeout and reclaim clocks
     meet at the same boundary.

5. **Windows file-sharing / atomic-replace assumptions**
   - A pattern that is atomic on POSIX is not automatically safe under concurrent
     Windows readers/writers.
   - The V1 SQLite journal is the truth; legacy JSON publish paths must not be
     revived as V1 state.

6. **Concurrent event loss**
   - Desktop/UI event handling must never become a second append-only truth store.
   - Desktop Hub consumes journal/projection/controller events and can always
     rebuild from the journal.

7. **Lease/reclaim race**
   - Exactly one claimant/reclaimer wins.
   - Timing-sensitive failures stay visible until the owning lane proves the race
     safe; they are not hidden as "random CI".

8. **EMFILE / process-descriptor exhaustion**
   - No uncontrolled watchers, helper spawning, retry storms, or unbounded open
     handles.
   - Raising OS limits is not the primary fix.

9. **Runtime state in git**
   - Runtime truth must never depend on a git commit/push/reconcile loop.

10. **Broken surface implies lost work** (incident 2026-10-02,
    `docs/WINDOWS_GUI_FREEZE_INCIDENT_2026-10-02.md`)
    - **A BROKEN SURFACE MUST NEVER IMPLY LOST WORK.**
    - WORK EXECUTION, SURFACE/UI, TERMINAL HOST, AGENT SESSION and PERSISTENT
      STATE are separate failure domains; losing one must not unnecessarily lose
      the others, and must never be reported as losing them.
    - The customer must be able to learn — without a working desktop — what is
      running, what is saved, and whether reboot is safe.

## 5. Chosen Windows process-safety direction

For L3 Windows worker execution, prefer **Windows Job Objects** for exact
Courier-owned process-tree containment.

Required behavior:
- create an owned job before/at child launch;
- assign the task process to the job immediately;
- use `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (or an equivalently proven
  process-tree mechanism);
- retain durable ownership metadata sufficient to diagnose a crash/restart;
- timeout -> graceful bounded termination attempt -> hard termination of only the
  owned tree -> verify zero owned survivors;
- unrelated processes must survive;
- if cleanup cannot be proven, enter a blocking resource/orphan state before any
  new task starts.

Do not use broad `taskkill`/name matching as the final containment contract.

Microsoft reference:
- Job Objects:
  https://learn.microsoft.com/windows/win32/procthread/job-objects
- JOBOBJECT_BASIC_LIMIT_INFORMATION:
  https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information

## 6. Chosen low-power direction

Courier should be **event-driven when idle**.

Rules:
- no busy loops;
- no high-frequency polling merely to prove a window/process is alive;
- no PowerShell/WMI subprocess every few seconds for routine health sampling;
- prefer in-process lightweight metrics (existing pinned `psutil` where it
  satisfies the evidence requirement);
- use bounded, adaptive backoff for unavoidable polling;
- stop non-essential timers/animation when hidden/minimized;
- background workers may opt into Windows EcoQoS only after correctness/process
  containment is proven;
- foreground UI, claim/heartbeat timing, verification, and latency-critical work
  must not be throttled in a way that risks correctness.

Microsoft explicitly recommends minimizing CPU wakeups/timers for background apps
and provides ProcessPowerThrottling / EcoQoS for non-foreground work.

References:
- Windows background power:
  https://learn.microsoft.com/windows/apps/performance/power
- ProcessPowerThrottling / EcoQoS:
  https://learn.microsoft.com/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessinformation

## 7. SQLite / Ledger health direction

The V1 journal already provides an append-only event chain and deterministic
projection. Keep that as the product truth.

Additional quality rules:
- invalid/corrupt chain -> controller read-only / blocked mode, never silent reset;
- duplicate event -> deterministic duplicate handling, never duplicate effect;
- replay projection must equal live projection;
- use a finite SQLite busy timeout rather than an unbounded wait;
- a successful write transaction is all-or-nothing;
- integrity diagnostics must never mutate customer truth.

Integrity checks:
- `PRAGMA quick_check` is the cheaper linear-time database structural check;
- `PRAGMA integrity_check` is deeper and more expensive;
- do not run a full integrity scan continuously in the foreground.

Preferred use:
- normal fast path: journal's own chain/invariant checks;
- after unclean shutdown or suspicious database error: bounded `quick_check`
  before re-enabling writes;
- diagnostics / clean-machine acceptance: full `integrity_check`;
- any failed integrity/chain check -> fail closed, preserve DB, offer diagnostics
  rather than "repairing" by deleting history.

SQLite references:
- PRAGMA quick_check / integrity_check:
  https://sqlite.org/pragma.html
- busy timeout:
  https://sqlite.org/c3ref/busy_timeout.html

## 8. Butter-smooth PC quality targets

These are product targets for the internal acceptance machine. They are
measurement targets, not permission to fake or skip work.

### Interaction targets

- input acknowledgement / button feedback: target <= 100 ms;
- common navigation / cached status: target <= 300-500 ms;
- useful first window/shell: target <= 2 s on the reference clean Windows 11
  machine;
- if an operation exceeds ~1 s, keep the window responsive and show truthful
  progress/status;
- no provider call, journal rebuild, filesystem scan, or heavy verification on
  the UI thread;
- long work remains cancellable where cancellation is safe.

If the current implementation misses a target, measure first and optimize the
bottleneck. Do not replace the locked architecture just to chase a benchmark.

Microsoft references:
- responsiveness:
  https://learn.microsoft.com/windows/apps/develop/performance/responsive
- keep the UI thread responsive:
  https://learn.microsoft.com/windows/apps/develop/performance/keep-ui-thread-responsive

### Idle targets

On a clean idle Home screen:
- no continuous task animation without real events;
- no tight timers;
- no repeated filesystem scans;
- no provider/API traffic merely to look active;
- no hidden heavy child process;
- zero Courier-owned orphan processes.

CPU/wakeup/RAM budgets should be measured on the clean-machine acceptance PC and
then pinned as regression thresholds. Do not invent a RAM number before a
baseline exists.

## 9. Customer error UX contract

Primary UI messages must answer:
1. What happened?
2. What happens next?
3. What, if anything, does the user need to do?

Rules:
- prevent known errors before showing messages where possible;
- no generic "Something went wrong" if Courier knows the actual class;
- no raw exception/traceback in normal UI;
- safest/non-destructive choice is the default;
- do not interrupt for non-actionable information;
- technical detail belongs under **Details** and in the redacted diagnostics
  bundle;
- every indefinite operation has a truthful state, not an endless spinner;
- if Courier self-recovers, prefer a quiet status rather than making the customer
  supervise the recovery.

Microsoft references:
- error-message guidance:
  https://learn.microsoft.com/windows/win32/debug/error-message-guidelines
- Windows writing style:
  https://learn.microsoft.com/windows/apps/design/style/writing-style

## 10. Stage gates — errors must be found before they leak downstream

### ACTIVE LEDGER may advance only when
- journal append is atomic;
- event identity/dedup is deterministic;
- hash/integrity failure fails closed;
- live projection == replay projection;
- restart preserves the same truth;
- no active V1 writer bypasses the controller/journal.

### RELIABLE AUTOMATION may advance only when
- L2 controller/API contract is green;
- worker process ownership is exact;
- timeout/cancel kills and reaps the owned tree;
- result outbox survives restart;
- heartbeat/lease timing has safety margin;
- resource probe cannot fail open;
- retries are finite;
- child output/logs are bounded;
- no new heavy work begins while cleanup is uncertain.

### GOLDEN PATH may advance only when
- synthetic happy path is live end-to-end;
- worker crash;
- duplicate result;
- stale/late result;
- timeout;
- cancellation;
- controller restart;
- corrupted/incomplete journal;
- uncertain non-idempotent effect -> BLOCKED
all have green targeted tests.

### DESKTOP HUB may advance only when
- UI is journal/controller driven;
- restart/replay reaches the same logical scene;
- duplicate/out-of-order live notifications cannot corrupt displayed truth;
- UI disconnect/reconnect self-recovers;
- degraded/blocked states are clear without raw internals;
- UI stays responsive while backend work runs.

### WINDOWS EXE may advance only when
- one per-user instance is enforced (`Local\\CourierV1` or proven equivalent);
- no Python installation is required;
- paths/logs/diagnostics are user-local;
- startup/shutdown are bounded;
- no orphan Courier process remains;
- idle behavior meets the measured power target.

### CLEAN-MACHINE ACCEPTANCE may advance only when
- install -> launch -> Golden Task -> close -> reopen -> deterministic replay
  passes on a clean Windows 11 machine;
- diagnostics are redacted and useful;
- uninstall preserves user data unless the user explicitly chooses removal;
- no hidden terminal or developer intervention is required.

### FREEZE / INTERRUPTION RECOVERY GATE
Cross-cutting. Required before **WINDOWS EXE** and **CLEAN-MACHINE ACCEPTANCE**
may advance. Created by the 2026-10-02 Windows GUI freeze
(`docs/WINDOWS_GUI_FREEZE_INCIDENT_2026-10-02.md`).

PASS only with evidence that Courier:
1. identifies its own active work (owned worktrees, tasks, processes);
2. knows the last accepted/checkpointed state;
3. preserves uncommitted meaningful work without altering the working state
   (patch/bundle outside the repo; no secrets, runtime DBs or session contents);
4. distinguishes surface failure from task failure;
5. distinguishes terminal-host failure from worker failure;
6. never kills unrelated processes (exact owned PIDs only, never by name);
7. writes a Recovery Receipt;
8. states `SAFE_TO_REBOOT` or `NOT_SAFE_TO_REBOOT` with reasons;
9. after restart, determines a safe resume point from durable state;
10. passes a controlled test proving whether work survives an interruption.

Required acceptance tests (synthetic, owned processes only):
- Explorer/UI freeze while a worker runs → work continues, status readable headlessly;
- terminal host death (integrated terminal / PowerShell Editor Services) → worker
  and state unaffected, classified `TERMINAL_HOST_FAILED`, not `WORK_FAILED`;
- IDE crash → uncommitted work recoverable, no task marked failed;
- Courier surface crash → controller/worker/journal continue; surface rebuilds;
- worker survives surface loss → result delivered and visible after surface returns;
- worker crashes while surface survives → surface shows honest failure, no fake progress;
- forced reboot after checkpoint → nothing after the checkpoint is claimed done;
- restart and verified continuation → resume point computed and verified, no
  duplicate effect.

Implementation workkeys (lane owner in brackets; PREP_ONLY until the owning
lane's stage gate is open):

| Workkey | Lane | Deliverable |
|---|---|---|
| FRZ-01 | L1 | **Right-host guard:** every ops/recovery entrypoint first proves host identity (hostname, OS, device ID) and stops on mismatch; device registry maps sessions to hosts. |
| FRZ-02 | L2 | **Headless status / Critical Snapshot L0:** one command + JSON file answering what runs, owned PIDs, last progress, dirty/unpushed state, resources; works with explorer/IDE frozen. |
| FRZ-03 | L3 | **Device Health sampler:** bounded periodic CPU/RAM/disk/handles + explorer/DWM responsiveness into the journal, so incidents have before/after evidence. |
| FRZ-04 | L1 | **Off-machine checkpoint:** cap unpushed commits/time per owned lane; auto push or `git bundle` of owned work; alert when over the cap. |
| FRZ-05 | L1 | **Work preservation without mutation:** recovery directory with status, diff, cached diff, untracked list, bundle and manifest; secret/runtime filters. |
| FRZ-06 | L2 | **Layered health model:** separate states for work, surface, terminal host, agent session, persistent state; classification enum incl. `TERMINAL_HOST_FAILED`, `SURFACE_CORRUPTED`. |
| FRZ-07 | L2 | **Reboot verdict + Recovery Receipt:** `SAFE_TO_REBOOT`/`NOT_SAFE_TO_REBOOT` with reasons; receipt with the fields of the incident record. |
| FRZ-08 | L3 | **Exact-owned recovery actions:** escalation ladder (wait → explorer restart on evidence → owned helper restart → owned tree kill) via Job Objects; never by name. |
| FRZ-09 | L2 | **Safe resume point + verified continuation** after restart from journal/outbox/git state. |
| FRZ-10 | L1 | **Interruption test harness:** the acceptance tests above as repeatable synthetic scenarios. |

## 11. Writer-lane activation and model-effort policy

Only L1 promotes/merges work into `integration/v1`.

Read-only preparation may run ahead. Writer implementation is activated by
evidence, not by a timer and not because credits are available.

### Claude Opus 5.5 effort

| Lane | Writer effort | Activation rule |
|---|---|---|
| L1 Integration / CI / Golden Harness | **Maximal** | Always active as integration owner |
| L2 Journal / Controller / API | **Maximal** | Active until controller/API/restart/corruption contract is integrated |
| L3 Bounded Worker Host | **Maximal** for process/resource safety; may drop to Extra High only for narrow follow-ups | Writer starts when the L2 command/event/lease interface it depends on is committed and green |
| L4 Verifier / Synthetic Adapter | **Extra High** | May start when result/evidence identity contract is stable; can overlap late L3 if files/contracts do not collide |
| L5 Desktop Hub / Replay | **High** | Writer starts after live Golden Path truth exists; prep may happen earlier |
| L6 Packaging / Launcher / Diagnostics | **Extra High** | Writer starts when app entrypoint/paths are stable; packaging prep may happen earlier |

Do not use Ultra/Ultracode by default. Reserve it for one narrowly identified
contradiction or review where Maximal/Extra High plus evidence did not settle the
problem.

### Muse preparation policy

- model: current `muse-spark-1.3-contributor`;
- reasoning: **xhigh** for V1 prep/audit;
- role: read-only evidence, failure mapping, test design, collision checking;
- no new product writer lane;
- no broad suite by default;
- no background watcher merely to spend quota;
- no prompt storms.

Subagents:
- default: **0**;
- at most **1 read-only** subagent for a narrow independent evidence question
  only when it materially reduces duplicate reading;
- no recursive subagents;
- under EMFILE/resource pressure: **0 subagents**.

### Opus writer subagents

Default: **0**.

A writer may use at most one read-only reviewer/specialist when:
- the question is narrow;
- it does not touch the writer's files;
- it returns evidence, not competing code;
- it cannot spawn further children.

No parallel writer subagents editing the same product scope.

## 12. Development-session lifecycle: /compact and /clear

This is developer/orchestrator workflow only. It is never part of the customer
product.

When a Muse session becomes large:

1. While an active task is still in progress, prefer `/compact`.
2. Before any session reset, persist a checkpoint/handoff with:
   - current repo HEAD;
   - role/lane;
   - completed evidence;
   - exact unfinished phase;
   - blockers;
   - next exact task.
3. Writer sessions also commit/push their owned work according to lane policy
   before resetting, unless the checkpoint explicitly says why they cannot.
4. Use `/clear` only at a clean phase boundary or when context is stale/poisoned
   after the checkpoint is durable.
5. After `/clear`, re-bootstrap from repo truth. Do not reconstruct from memory.

Important Muse behavior:
- `/compact` summarizes old context and keeps the session;
- `/clear` starts a fresh session and clears the visible scrollback;
- `/clear` resets conversation context, goal, tasks and token counts;
- on-disk project rules/memory are not erased.

Therefore: **checkpoint first, /clear second, bootstrap third.**

Official Muse reference:
https://dev.meta.ai/docs/muse-code/interactive

## 13. Fresh-chat continuity

A new ChatGPT/Opus/Muse session must not make the owner explain the product again.

FIRST READ:
1. `docs/V1_RULE_0.md`
2. `docs/V1_PRODUCT_QUALITY_BAR.md`
3. `docs/NEXT_CHAT_HANDOFF.md`
4. newest relevant GitHub Issue #54 rules
5. CURRENT `integration/v1`
6. `docs/v1/INTEGRATION_LOG.md`

Then continue the first unproven gate.

Do not reopen old NIGHT/30x/100x/YOLO writer plans.

## 14. Current phase when this contract was authored

Verify again before acting.

At authoring time:
- L2 core journal/state-machine/projection had been integrated as Step 9;
- Golden harness still needed `courier_core.serve`, `courier_worker.host`,
  and `adapters.synthetic`;
- the next active product path was L2 Controller/API -> L3/L4 -> live Golden Path.

The durable rule is the stage gate, not this historical snapshot.

---

**QUALITY RULE: Courier may be technically complex inside, but it should feel
quiet, safe, light, fast, and obvious to the customer.**
