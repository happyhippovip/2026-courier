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
