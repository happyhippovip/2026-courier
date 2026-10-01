# Courier Symphony V1 — Orchestration Playbook

Status: **AUTHORITATIVE DEVELOPMENT ORCHESTRATION PLAYBOOK**

Purpose: make Courier development reproducible across ChatGPT, Claude/Opus, Muse, Google Antigravity, Windows, Mac, CI, and future chats without making Dennis reconstruct the process each day.

This file governs **how development work is orchestrated**. It does not change the locked runtime architecture.

Read with:
- `docs/V1_RULE_0.md`
- `docs/V1_PRODUCT_QUALITY_BAR.md`
- `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
- `docs/NEXT_CHAT_HANDOFF.md`
- newest relevant GitHub Issue #54 rules
- CURRENT `integration/v1`
- `docs/v1/INTEGRATION_LOG.md`

## 1. Core model

Courier has two different layers:

### Product implementation
Only six writer lanes:
L1-L6.

### Development orchestration
May use many logical tasks, scouts, reviewers, workflows, skills, and queues, but they do **not** become writer lanes.

Aggressive work comes from:
- deep queues;
- staged workflows;
- independent read-only evidence gathering;
- verifier/reconciler passes;
- bounded live concurrency.

Aggressive work does **not** mean:
- 30/65/100 identical prompts;
- dozens of simultaneous local agents;
- overlapping writers;
- retry storms;
- repeated whole-repo scans.

## 2. Current-source rule

Every orchestration cycle starts by verifying:
- CURRENT `integration/v1` SHA;
- open L1-L6 branches/PRs;
- newest relevant Issue #54 rules;
- latest integration log;
- current Golden missing modules/gates.

Never assign from an old SHA merely because it is in a prompt or handoff.

Local process/workflow liveness is **not GitHub truth**. It must be checked from the actual host/window before clear/close/reassignment.

## 3. Claude / Opus policy

Opus is for implementation and hard reconciliation, not broad duplicated scouting.

Default effort:
- L1: Maximal
- L2: Maximal
- L3: Maximal for process/resource safety; Extra High for narrow follow-ups
- L4: Extra High
- L5: High
- L6: Extra High

Writer rule:
- one official writer per active lane;
- default zero writer subagents;
- at most one narrow read-only specialist/reviewer if it materially reduces uncertainty;
- L1 alone promotes/merges into `integration/v1`.

When a lane is blocked on another lane's contract, mark WAIT_FOR_<LANE> and continue only independent work.

## 4. Muse policy

Muse is optimized here for read-only prep, adversarial review, test design, collision detection, and large staged factories.

### Prefer workflows over prompt storms

For workflow-scale work, use a normal prompt that explicitly requests a workflow.

Do not require `/goal` for a factory. If a session has Goal Store provenance/backend errors, do not keep retrying `/goal`; use a fresh retained session and a workflow that does not depend on Goal Store.

Use `/settings -> Tools -> Workflows -> explicit` or `auto`.

### Session retention

Do not start important overnight workflows with `--no-session-log`.

Retained sessions support workflow recovery after restart. A failed workflow can be recovered/resumed using Muse's retained workflow records when supported by the installed build.

### Monitoring

Use bounded checks:
- `/workflows` for workflow progress/status;
- `/recap` after stepping away;
- `/compact` when active context is large.

Do not poll continuously.

### Mac concurrency

Because Courier already experienced real EMFILE/resource pressure:
- prefer one or a few long workflows over many GUI sessions;
- cap local investigator fanout conservatively;
- current factory template uses at most 3 active investigator children at once;
- verifier runs after investigators finish;
- no recursive child fanout;
- any EMFILE / os error 24 / host-pressure signal stops new child launches.

### Factory pattern

Preferred factory structure:

3 investigators
-> wait
-> 1 verifier/reconciler
-> persist synthesis
-> next wave

This gives high total task count with bounded live process count.

Canonical large template:
`docs/v1/orchestration/MUSE_144_FACTORY_TEMPLATE.md`

## 5. Google Antigravity policy

Use Antigravity for deep read-only review, research, independent verification, and reusable orchestration.

### Persistent constraints: Rules

Antigravity discovers persistent workspace rules from files such as `AGENTS.md`, `GEMINI.md`, and `.agents/rules/*.md`.

Courier therefore keeps the essential bootstrap in repository `AGENTS.md`.

### Repeatable multi-step behavior: Skills

As of 2026-10-01, Antigravity's legacy Workflows are deprecated and scheduled to retire on 2026-11-01. New durable Courier automation should therefore prefer **Agent Skills** over new legacy Antigravity Workflow files.

Workspace skill:
`.agents/skills/courier-orchestrate/SKILL.md`

Invoke with:
`/courier-orchestrate`

Skills support progressive context loading and bundled references/assets, which is preferable to one giant permanent prompt.

### Background subagents

Antigravity supports asynchronous background subagents. Use them for independent evidence questions, not overlapping implementation.

Bound concurrency. If the local host shows pressure, stop new subagents.

### /learn

Antigravity `/learn` can distill a successful recent procedure into a persistent project Rule or Skill. Use it only after the procedure is proven useful; review generated files before treating them as canonical.

## 6. Daily operating cycle

### Morning Sync

1. Verify current `integration/v1`.
2. Read latest Issue #54 + integration log.
3. Inspect current official writer branches/PRs.
4. Inspect overnight Muse workflow status/artifacts.
5. Inspect Antigravity results/artifacts.
6. Run custody checks on old/unknown windows.
7. Deduplicate findings.
8. Promote only evidence-backed work to L1-L6.
9. Close/clear only windows proven safe.
10. Produce today's exact writer activation order.

Morning output:
- CURRENT_HEAD
- ACTIVE_WRITERS
- READY_LANES
- WAITING_LANES
- REAL_BLOCKERS
- GOLDEN_BLOCKERS
- WINDOWS_BLOCKERS
- SAFE_MERGE_ORDER
- WINDOWS_TO_KEEP
- WINDOWS_SAFE_TO_CLOSE

### Workday

- Opus writers implement only their lane.
- Muse/Antigravity may prepare later stages read-only.
- CI/healthy Windows execute platform-specific gates.
- Mac remains coordination/read-only when resource pressure exists.
- L1 integrates one proven lane delivery at a time.

### Pre-sleep / Overnight

1. Verify current head.
2. Inventory active windows/processes/workflows.
3. Run custody on unknown windows.
4. Do not start another heavy Mac workflow if an existing factory is healthy and sufficient.
5. Queue deep work in bounded factories.
6. Persist factory output locations.
7. Ensure no duplicate factories cover the same scope.
8. Keep official writers separate from read-only factories.
9. Do not schedule repeated no-op polling merely to keep agents active.

### Wake / Harvest

1. `/workflows` on retained Muse factory owners.
2. `/recap` where useful.
3. Harvest final artifacts/checkpoints.
4. Reconcile duplicates/contradictions.
5. Map findings to L1-L6.
6. Update durable continuity only with real transitions.
7. Re-run custody and close stale completed windows.
8. Start next lane only when its activation gate is met.

## 7. Window custody integration

Before `/clear`, close, or repurpose:
read `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`.

Invariant:

**checkpoint first -> durable handoff second -> clear/close third**

Unknown state means not safe to clear/close.

Active workflows are protected from clear/close until completion or explicit recoverable stop + durable handoff.

## 8. Durable vs volatile state

Do not confuse these.

### Durable canonical state
Store in GitHub:
- architecture/product rules;
- integration evidence;
- lane merge results;
- reusable orchestration procedures;
- important cross-chat rules.

### Volatile host/session state
Do not pretend GitHub can know this automatically:
- whether a terminal is still running;
- whether a local workflow is alive;
- process IDs;
- transient local checkpoints;
- current resource pressure.

Refresh volatile state from the host at the beginning of an orchestration turn.

## 9. Self-updating continuity rule

"Always updated" means **verify then refresh**, not blindly trusting a static document.

Every new orchestration chat must:
1. read `AGENTS.md`;
2. read canonical V1 docs;
3. query CURRENT GitHub state;
4. compare it with handoff snapshots;
5. explicitly correct stale anchors;
6. continue from the first unproven gate.

After a major transition, L1/orchestrator should update:
- `docs/v1/INTEGRATION_LOG.md`;
- `docs/NEXT_CHAT_HANDOFF.md` when the critical path materially changes;
- Issue #54 when a durable orchestration/product rule changes.

Do not auto-commit transient process/window state to the repo.

## 10. Orchestration improvement loop

When a new orchestration technique proves useful:

1. test it on a bounded scope;
2. measure whether it reduced owner effort, duplicate reading, resource pressure, or missed errors;
3. document failures/limits;
4. add it to this playbook or a reusable Skill/template;
5. remove obsolete instructions;
6. keep one canonical method instead of stacking contradictory prompts.

This is how the orchestration system improves every day without becoming another product architecture.

## 11. Current preferred reusable assets

- `AGENTS.md` — cross-agent project bootstrap
- `docs/V1_ORCHESTRATION_PLAYBOOK.md` — this playbook
- `docs/V1_WINDOW_CUSTODY_PROTOCOL.md` — safe clear/close/repurpose
- `docs/v1/orchestration/MUSE_144_FACTORY_TEMPLATE.md` — large bounded Muse factory
- `.agents/skills/courier-orchestrate/SKILL.md` — Antigravity daily orchestration skill

## 12. Non-goals

Do not turn development orchestration into another permanent product dependency.

Courier V1 must still ship as a bounded Windows application independent of AI development windows.

RULE 0.000000000 remains:

**FINISH THE PRODUCT.**

## 13. Workflow failure-domain recovery

When a long-running Muse factory is active, distinguish three failure domains before acting.

### A. Monitor/foreground model transport failure

Example:
- a status-checking foreground turn reports a provider transport error after retries;
- the retained workflow still reports `running`.

This does **not** by itself prove the workflow failed.

Action:
1. stop foreground polling;
2. do not re-submit the factory prompt;
3. wait for the current workflow attempt to settle or produce terminal delivery;
4. later perform one bounded `/workflows` check;
5. only recover/resume if the workflow itself is failed/stopped.

### B. Local host/resource failure

Examples:
- `Too many open files`;
- `EMFILE`;
- `os error 24`;
- repeated shell/file spawn failures.

Action:
- mark RESOURCE_PAUSE for new local helper launches;
- do not use `ls`/probe/retry loops simply to watch progress;
- do not start more Mac factories/subagents;
- preserve the active retained workflow;
- free only windows/processes that are independently proven safe by the custody protocol.

Host resource failure and provider transport failure are separate evidence and must not be conflated.

### C. Workflow child failure

A child task may fail while the workflow owner remains healthy.

Action:
- let the workflow verifier/reconciler classify/retry only according to the workflow contract;
- do not restart the whole 144-task factory because 1-2 children failed;
- terminal synthesis must record failed/blocked children honestly.

### Retained workflow recovery

For a retained Muse session, if the **workflow itself** fails or the Muse process exits:

- do not paste the full factory prompt again;
- wait until the current owner is no longer running;
- recover/resume the retained workflow using the persisted workflow records/run id;
- same-process resume should reuse the existing workflow script/run id when available;
- after process restart, use Muse's retained workflow recovery mechanism for the run/session;
- resume should reuse the longest unchanged prefix of completed child work rather than rerunning everything.

Never run two owners for the same workflow concurrently.

### Polling rule

Do not create a 4-minute wait/check loop around `/workflows`.
The factory is background work; let terminal delivery wake the session when possible.

A useful owner interaction is:
- start factory;
- confirm once that it is running;
- step away;
- on return use `/recap` or one `/workflows` check;
- recover only if terminal state requires it.

This reduces provider calls, host probes, tokens, wakeups, and accidental interference.


## 14. Mac low-FD mode supersedes child factories under active EMFILE

A large logical queue does not require child-agent fanout.

If the Mac has current/recent EMFILE, child-session lease failures, or sustained heat:
- do not launch another 144-child factory;
- do not launch new Muse child agents/subagents on that host;
- prefer one retained Muse session processing a long logical queue sequentially;
- canonical template: `docs/v1/orchestration/MUSE_MAC_LOW_FD_SINGLE_AGENT.md`.

Return to bounded child workflows only after host stability is separately proven.

The failed 144-cell run is treated as orchestration-infrastructure evidence, not product-code evidence.

## 15. Human-time / master-prompt rule

**Dennis is not the router. Minimize manual copy/paste operations.**

Default response behavior for orchestration:
- if many related read-only tasks share the same repo context and can run safely in one session, bundle them into **one master prompt**;
- one paste per window by default;
- put the queue, phases, checkpoints, stop conditions, and final synthesis inside that prompt;
- do not make Dennis manually paste M-R01, M-R02, M-R03... unless separate windows are technically necessary;
- if multiple windows are truly useful, provide one master prompt **per window**, not one tiny prompt per subtask;
- split only for a concrete reason: writer ownership, platform isolation, process isolation, context limits, collision risk, or resource pressure;
- say the exact model/effort and exact paste count.

Preferred hierarchy:
1. one master prompt in one existing safe window;
2. one master prompt per genuinely independent window;
3. a bounded workflow/skill when agent-native orchestration is useful;
4. many small manual prompts only as a last resort.

Reusable 14-phase Muse master prompt:
`docs/v1/orchestration/MUSE_MASTER_14_PHASE_PROMPT.md`

This rule exists to save owner time and reduce transcription mistakes while keeping work deep and auditable.

## 16. Muse unattended serial loop and duration truth

For one-window unattended Muse work, prefer a scheduled serial loop over manually queueing dozens or hundreds of identical messages.

Project skill:
`.agents/skills/courier-night-loop/SKILL.md`

Recommended invocation after the skill is available in the checkout:

```
/loop 5m /courier-night-loop
```

Why:
- Muse runs the recurrence in the same retained session;
- an occurrence that lands while an active turn is still running is skipped rather than piled into a backlog;
- each invocation reads durable local state and performs one new deep evidence unit;
- when the repo head changes it starts a new evidence epoch and refills the backlog;
- if no honest work exists it idles rather than inventing work;
- EMFILE/resource pressure becomes sticky RESOURCE_PAUSE rather than a retry storm.

**Do not promise runtime from prompt size or queue length.** A huge prompt may finish in minutes. Queueing the same prompt 5,000 times does not create 5,000 useful minutes, and repeated identical work can become duplicate/no-op work.

If the installed Muse build is 1.4.0+, Meta's changelog says a newly-created `/loop` runs until deleted. Older documentation still describes a seven-day expiry, so verify the installed build and stored job rather than guessing.

The Muse process/session must be running for scheduled work to fire. A retained session can be resumed later.

### Windows-specific Muse rule

Muse inter-session peer messaging is currently unavailable on Windows. Therefore do not design Windows orchestration around many independent Muse windows coordinating with each other.

Preferred Windows Muse pattern:
- ONE retained Muse steward window;
- `/loop 5m /courier-night-loop`;
- read-only;
- xhigh/max as budget allows;
- no manual prompt flood;
- close old completed Muse windows after custody proves them safe.

### Antigravity parallelism

When genuine parallel read-only research is useful, prefer one Antigravity control-room session with several non-overlapping asynchronous background subagents rather than making Dennis manually maintain many terminals.

Start conservatively with up to 4 independent read-only subagents on a healthy host. Increase only when work is truly independent and there is no resource pressure. Monitor from Antigravity's `/agents` panel.

This preserves real parallelism while reducing owner routing work.

## 16. Owner-away / self-refilling queue protocol

For short absences (shower, errands, roughly one hour) and sleep periods, use:
`docs/v1/orchestration/AWAY_QUEUE_REFILL_PROTOCOL.md`.

Key rule:

**one owner session -> durable queue state -> self-refill from current evidence -> dedupe -> bounded useful unit -> repeat**

Muse Mac:
- primary = `/loop 5m /courier-night-loop`;
- emergency A/B/C refill prompts are available when the loop is unavailable;
- do not manually stack hundreds of Muse messages.

Antigravity:
- one self-refilling ledger;
- repeatable NEXT UNIT token may be queued deeply only if the session executes queue items serially.

A self-refilling queue may generate new work only from CURRENT evidence. It must idle rather than invent work when nothing honest remains.
