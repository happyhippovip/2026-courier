# NEXT CHAT HANDOFF — Courier Symphony

**Purpose:** First-read continuity for every new ChatGPT / Opus / Muse / Courier session.

## 0. Identity — do not get this wrong

- **Company / product:** Courier Symphony
- **Repository:** happyhippovip/2026-courier
- **V1 integration trunk:** `integration/v1`
- **North star:** `docs/V1_RULE_0.md`
- **Quality / customer-experience contract:** `docs/V1_PRODUCT_QUALITY_BAR.md`
- **Canonical continuity thread:** GitHub Issue #54
- **Integration evidence:** `docs/v1/INTEGRATION_LOG.md`
- **Orchestration playbook:** `docs/V1_ORCHESTRATION_PLAYBOOK.md`
- **Window custody:** `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
- **Cross-agent bootstrap:** `AGENTS.md`
- **Antigravity daily skill:** `.agents/skills/courier-orchestrate/SKILL.md`

A fresh session must not make the owner re-explain the company, destination,
lane model, or current critical path.

## 1. Rule 0.000000000

**FINISH THE PRODUCT.**

Primary route:

**ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY**

Do not redesign the destination unless CURRENT implementation evidence proves a
specific contract contradiction.

PC/Windows first. Mobile comes later and must reuse the same canonical runtime
truth.

## 2. Customer experience north star

Courier may be technically complicated internally; it must feel simple to the
customer.

The customer must not need to understand:
- terminals;
- prompts;
- L1-L6;
- GitHub;
- model/effort settings;
- `YOLO`;
- `/goal` or `/clear`;
- branches/worktrees;
- subagents;
- stack traces or internal error jargon.

Courier should self-recover when recovery is safe and truth is known. Ask the
user only for a real permission, consequential decision, or ambiguous
non-idempotent outcome.

Normal product UI is plain-language and calm. Raw technical detail belongs in
**Details / Diagnostics**.

The Windows app should be quiet, light, responsive, local-first and useful even
when optional providers are unavailable.

The complete quality bar and error gates are in:
`docs/V1_PRODUCT_QUALITY_BAR.md`.

## 3. Product value

Courier Symphony should reduce repeated computer work.

Core value:
- email triage / handling;
- user-selected local file and data organization;
- repetitive digital housekeeping;
- reliable task execution and verification;
- restart/recovery without duplicate work;
- evidence, replay and diagnostics.

Local-first/privacy:
- never upload private files merely because Courier can access them;
- operate only inside user-selected scopes;
- consequential external actions require the product contract/permission;
- deterministic local work should not burn paid model/API capacity.

Credits fund optional paid capability that creates visible value. Never promise
guaranteed profit or literally zero total operating cost.

## 4. Locked V1 architecture

Dennis + ChatGPT + Opus reconciled the V1 architecture.

Locked direction:
- one integration trunk: `integration/v1`;
- only six implementation lanes L1-L6;
- runtime state leaves git;
- SQLite append-only event journal is canonical truth;
- deterministic projections;
- one controller;
- bounded worker hosts;
- one verifier path;
- synthetic + local_shell first for internal EXE;
- Desktop Hub is a view of journal/controller truth, never a second orchestrator;
- deterministic replay is first-class;
- Windows V1 packaging: PyInstaller onedir + per-user Inno Setup;
- Mac coordination stays read-only while host resource pressure/EMFILE is active;
- healthy Windows + CI are execution/build authority;
- old NIGHT/30x/100x/YOLO writer swarms are frozen.

## 5. Ledger status and Golden Path

Runtime truth is:

**SQLite append-only journal -> deterministic projection -> controller -> worker -> verifier -> UI**

Golden lifecycle:

TASK_CREATED
-> TASK_CLAIMED
-> TASK_STARTED
-> RESULT_READY
-> RESULT_ACCEPTED
-> TASK_COMPLETE
-> shutdown
-> restart
-> deterministic replay to the same final state

Failure gates include:
- worker crash;
- duplicate result;
- stale/late result;
- timeout;
- cancellation;
- controller restart;
- corrupt/incomplete journal;
- uncertain non-idempotent result -> BLOCKED, never blind retry.

At the verified anchor recorded below, the L2 journal/state-machine/projection
core was already integrated. Do not redo it.

## 6. Six V1 writer lanes only

- **L1:** Integration / CI / Golden Harness
- **L2:** Journal / Controller / API
- **L3:** Bounded Worker Host
- **L4:** Verifier / Synthetic Adapter
- **L5:** Desktop Hub / Replay
- **L6:** Packaging / Launcher / Paths / Logging / Diagnostics

Everyone else is read-only review/evidence/test design unless Dennis explicitly
changes Rule 0.

Only L1 promotes/merges work into `integration/v1`.

Writer activation is evidence-gated:
- L2 remains active until controller/API/restart/corruption semantics are green;
- L3 writer starts when the L2 command/event/lease interface it needs is committed
  and green;
- L4 may start when result/evidence identity is stable and may overlap late L3
  without file/contract collisions;
- L5 writer starts after live Golden Path truth exists;
- L6 writer starts when app entrypoint/paths are stable, though read-only packaging
  prep may happen earlier.

## 7. Model / effort policy

Claude Opus 5.5:
- **L1: Maximal**
- **L2: Maximal**
- **L3: Maximal for process/resource safety; Extra High only for narrow follow-ups**
- **L4: Extra High**
- **L5: High**
- **L6: Extra High**

Ultra/Ultracode is not a default. Reserve it for one narrowly proven unresolved
contradiction/review.

Muse prep:
- current model: `muse-spark-1.3-contributor`;
- reasoning: **xhigh**;
- read-only evidence/test/failure mapping;
- default subagents: **0**;
- at most one narrow read-only subagent when it materially reduces duplicate
  reading;
- no recursive subagents;
- under resource pressure/EMFILE: zero subagents.

Opus writer subagents:
- default zero;
- at most one read-only specialist/reviewer for a narrow independent question;
- no parallel writer subagents touching the same product scope.

## 8. Orchestration / developer session lifecycle

For daily/overnight orchestration read `docs/V1_ORCHESTRATION_PLAYBOOK.md`.
For any old/unknown window read `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`.

Preferred pattern: deep queued workflows/skills with bounded live concurrency, not repeated identical prompt storms. The reusable Muse large-factory template is `docs/v1/orchestration/MUSE_144_FACTORY_TEMPLATE.md`. The reusable one-window 14-phase master prompt is `docs/v1/orchestration/MUSE_MASTER_14_PHASE_PROMPT.md`. For unattended serial Muse work, use `.agents/skills/courier-night-loop/SKILL.md` via `/loop 5m /courier-night-loop` when that skill exists in the current checkout.

Antigravity: prefer the repository Agent Skill `.agents/skills/courier-orchestrate/SKILL.md` for durable repeatable orchestration. Legacy Antigravity Workflows are being retired by Google on 2026-11-01; Skills are the durable path.

Custody invariant: **checkpoint first -> durable handoff second -> clear/close third.** Unknown custody is never safe to clear/close.

### Developer session lifecycle: /compact and /clear

This is developer workflow only; customers never see or use it.

When Muse context grows:
1. During active work, prefer `/compact`.
2. Before reset, write a durable checkpoint/handoff:
   - current HEAD;
   - role/lane;
   - completed evidence;
   - first unfinished phase;
   - blockers;
   - next exact task.
3. Writer sessions also commit/push owned work when lane policy requires it.
4. Use `/clear` only after that checkpoint at a clean phase boundary or when
   context is stale/poisoned.
5. After `/clear`, bootstrap from repo truth.

Important:
- `/compact` summarizes old model-visible context;
- `/clear` starts a fresh session and clears scrollback;
- `/clear` resets conversation context, goals, tasks and token counts;
- on-disk project rules/memory remain.

Rule: **checkpoint first -> /clear second -> bootstrap third.**

## 9. Known error classes that must not reach customers

Read `docs/V1_PRODUCT_QUALITY_BAR.md` for full detail.

Mandatory prevention includes:
- timeout leaving child/grandchild processes alive;
- fail-open resource probes;
- unbounded stdout/stderr/log growth;
- heartbeat/lease timing collision;
- Windows concurrent file/event loss;
- lease/reclaim races;
- EMFILE/process exhaustion;
- runtime truth returning to git;
- raw internal errors leaking into customer UX.

Never hide a new correctness regression by adding it to a baseline.

## 10. Desktop identity

Courier metaphor:
- Courier robots;
- packages/tasks;
- Queue;
- Worker Bays;
- Customs/ZOLL;
- Returns/Retry;
- Delivered;
- Human Desk.

Robots visualize real journal state. No fake busy motion.

V1: robots inside Courier Hub.
After internal EXE: transparent desktop overlay.
Later: robots may move toward real windows/apps.

The overlay reuses the same journal truth and never becomes another orchestrator.

## 11. Continuity / handoff rule

Every major transition:
- verify current `integration/v1` first;
- read Rule 0 + Product Quality Bar + newest Issue #54 rules;
- remove stale historical instructions;
- record current writer branches/SHAs only after verification;
- record one next critical path;
- record blockers;
- do not make the owner explain Courier Symphony again.

A handoff is bad if the next chat must rediscover:
company name, product goal, ledger architecture, lane model, current integration
state, current active stage, or next exact task.

## 12. Verified anchor at this handoff update

**Historical snapshot only — verify again before acting.**

At update time (2026-10-07):
- `integration/v1` = `498cb57a` (latest integration head);
- the V1 locked route (`ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY`) has been completely merged;
- L5 (PR #122) and L6 (PR #130) have been successfully merged.
- L10 Codex Provider Continuity (PR #128) has been successfully merged.
- L11 Antigravity Grep Rule (PR #131) has been successfully merged.
- L2 Agent Warehouse Bootstrap (PR #121) has been successfully merged.
- next critical implementation path:
  **EXTENDED INTEGRATIONS** (Cost-Aware Provider Routing Issue #118).

Never trust this SHA after new work without checking GitHub.

## 13. What a new chat does first

1. Say **Courier Symphony**.
2. Verify CURRENT `integration/v1`.
3. Read:
   - `docs/V1_RULE_0.md`
   - `docs/V1_PRODUCT_QUALITY_BAR.md`
   - this handoff
   - newest relevant GitHub Issue #54 rules
   - `docs/v1/INTEGRATION_LOG.md`
4. Inspect current L1-L6 state.
5. Continue the first unproven gate.
6. Do not restart architecture brainstorming.

## 14. Response style for the owner

- German unless asked otherwise.
- Direct and copy/paste-ready.
- Label MAC vs WINDOWS where relevant.
- For prompts: exact window/lane, exact model effort, exact paste count.
- HUMAN-TIME RULE: when several related Muse/read-only tasks can share one context safely, consolidate them into ONE master prompt per window by default; do not make Dennis manually paste a long sequence of tiny prompts.
- Say when `/compact` or `/clear` is appropriate.
- Verify current repo evidence instead of guessing.
- Do not give dozens of conflicting next steps.
- Never promise that a giant prompt or N queued duplicates will run for N minutes. For long-running Muse work prefer a real `/goal`, workflow, or `/loop` depending on the job.
- On Windows, prefer one retained Muse steward window for recurring read-only work; Muse peer-session messaging is not available on Windows.
- For true parallel read-only fan-out, prefer one Antigravity control room with bounded asynchronous subagents rather than making Dennis manually route many terminals.

---

## One-line bootstrap

**Courier Symphony — verify CURRENT integration/v1, then read AGENTS.md + docs/V1_RULE_0.md + docs/V1_PRODUCT_QUALITY_BAR.md + docs/V1_ORCHESTRATION_PLAYBOOK.md + docs/V1_WINDOW_CUSTODY_PROTOCOL.md + docs/NEXT_CHAT_HANDOFF.md + newest GitHub Issue #54 + docs/v1/INTEGRATION_LOG.md; keep the Dennis+ChatGPT+Opus V1 architecture locked and continue the next unproven gate on EXTENDED INTEGRATIONS.**
