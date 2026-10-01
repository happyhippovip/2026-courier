# NEXT CHAT HANDOFF — Courier Symphony

**Purpose:** This is the first thing a new ChatGPT/Opus/Courier agent should read so the project does not lose its identity or restart from zero.

## 0. Identity — do not get this wrong

- **Company / product name:** Courier Symphony
- **Repository:** happyhippovip/2026-courier
- **Project shorthand:** Courier
- **V1 north-star file:** docs/V1_RULE_0.md
- **Canonical continuity thread:** GitHub Issue #54
- **Current V1 integration branch:** integration/v1

A previous fresh chat did not even know the company/project name at the start. That continuity failure is unacceptable for Courier Symphony. Every future handoff should improve on the previous one: shorter to load, harder to misunderstand, and more current.

## 1. Rule 0.000000000

**FINISH THE PRODUCT.**

The destination is not another swarm experiment, another planning document, or another pile of branches.

The destination is a real Windows application people can install and use.

Primary route:

**ACTIVE LEDGER -> RELIABLE AUTOMATION -> GOLDEN PATH -> DESKTOP HUB -> WINDOWS EXE -> CLEAN-MACHINE ACCEPTANCE -> REAL ADAPTERS -> DESKTOP ROBOT OVERLAY**

Do not redesign this destination unless current implementation evidence proves a specific contract problem.

## 2. Product vision

Courier Symphony should reduce repeated computer work so much that users want to keep using it.

Core user value:
- email triage / email handling;
- local file and data organization;
- repetitive digital housekeeping;
- task execution and verification;
- restart/recovery without duplicate work;
- evidence, replay, and diagnostics.

The product should make organization feel unusually satisfying and easy enough to become a strong daily habit. **Do not use manipulative addiction mechanics.** The desired effect is that sorting/clean-up feels rewarding because Courier visibly removes friction and gets real work done.

A practical first value surface after the runtime is stable is email triage because it is easy for users to understand:
- categorize;
- summarize;
- surface action items;
- draft;
- archive/move/tag only under explicit user authorization.

Then extend the same organization model to user-selected local files/data.

Local-first/privacy principle:
- do not upload private files merely because Courier can access them;
- work only inside user-selected scopes;
- explicit permission for consequential external actions;
- local deterministic work should not consume paid model/API capacity unnecessarily.

## 3. Credits / commercial north star

Credits are for optional paid capability that creates visible value.

The aspiration is:
- users voluntarily replenish credits because Courier saves enough time, removes enough repetitive work, or enables enough useful work that credits feel worth buying again;
- show what credits funded;
- avoid burning credits to simulate activity;
- keep local deterministic operations low-cost.

Never promise guaranteed financial profit or literally zero total operating cost.

## 4. Final V1 architecture baseline

Dennis + ChatGPT + Opus reconciled the V1 architecture.

Do not reopen the entire architecture discussion unless implementation evidence forces it.

Locked direction:
- one integration trunk: integration/v1;
- maximum six V1 writer lanes;
- runtime state leaves git;
- SQLite append-only event journal is canonical truth;
- deterministic projections;
- one controller process;
- bounded worker hosts;
- one verifier path;
- synthetic + local_shell first for internal EXE;
- Desktop Hub is a view of journal truth, not a second orchestrator;
- deterministic replay is a first-class feature;
- Windows V1 packaging: PyInstaller onedir + per-user Inno Setup;
- Mac remains coordination/read-only while EMFILE/resource exhaustion persists;
- CI + healthy Windows host are execution/build authority;
- old 30x/100x/NIGHT/YOLO/loop writer swarms are frozen.

## 5. Ledger — this must finally become active

The Ledger is not another future feature.

V1 runtime truth must become:

**SQLite append-only journal -> deterministic projection -> controller -> worker -> verifier -> UI**

Minimum Golden Path:

TASK_CREATED
-> TASK_CLAIMED
-> TASK_STARTED
-> RESULT_READY
-> RESULT_ACCEPTED
-> TASK_COMPLETE
-> shutdown
-> restart
-> deterministic replay to the same final state

Failure gates:
- worker crash;
- duplicate result;
- late/stale result;
- timeout;
- cancellation;
- controller restart;
- corrupt journal detection;
- non-idempotent uncertain result -> BLOCKED, not blind retry.

Until this is green, do not claim the autonomous runtime is finished.

## 6. Six V1 writer lanes only

- **L1:** Integration / CI / Golden Harness
- **L2:** Journal / Controller / API
- **L3:** Bounded Worker Host (Mac + Windows)
- **L4:** Verifier / Synthetic Adapter
- **L5:** Desktop Hub / Deterministic Replay / Robots
- **L6:** Packaging / Launcher / Paths / Logging / Diagnostics

Everyone else:
- read-only review;
- test review;
- evidence;
- handoff;
- no new implementation branches unless Dennis explicitly changes Rule 0.

## 7. Desktop identity

Courier Symphony should stay visually unique.

The product metaphor:
- Courier robots;
- packages/tasks;
- Queue;
- Worker Bays;
- Customs/ZOLL verification;
- Returns/Retry;
- Delivered;
- Human Desk for blocked work.

Important:
- robot motion reflects real journal events;
- no fake busy motion;
- UI is never the source of truth;
- same journal replay => same logical scene.

V1:
- robots inside the Courier Hub window.

After internal EXE:
- transparent desktop overlay.

Later:
- robots can move toward actual application/window locations.

## 8. Continuity is itself a product requirement

Courier Symphony should eventually solve the same continuity problem its own development has suffered from.

A new agent should not ask:
"What is the project?" or "What is the company called?"

Future Courier concept:
- project identity;
- current state;
- recent changes;
- canonical rules;
- current ledger/runtime status;
- compact machine-readable project passport/context endpoint.

But **do not delay V1 EXE for a large context-server project now**.

For now continuity is:
1. this handoff;
2. docs/V1_RULE_0.md;
3. GitHub Issue #54;
4. current integration/v1 state.

## 9. Handoff quality rule

Every day / major chat transition:
- update current branch/SHA only after verifying it;
- remove stale instructions;
- record what is actually running;
- record the one next critical path;
- record blockers;
- keep the handoff copy-pasteable;
- do not make the user explain the company/project again.

A handoff is bad if the next chat needs several messages to rediscover:
- company name;
- product goal;
- ledger architecture;
- current integration branch;
- six-lane model;
- next exact task.

## 10. Current verified anchors at time this handoff was written

Verify these again before acting:
- integration/v1 existed at e95aa787bdff0740bd8f925ce7462827a9bf999c at the last check.
- docs/V1_RULE_0.md was created on branch lane/L1-product-rule-zero, commit dd207057848c6d55ee43f0ea5ca413e977ac9d43, awaiting normal L1 integration.
- GitHub Issue #54 is the canonical orchestration/continuity thread.

Do not trust any historical SHA blindly after a new work cycle.

## 11. What the next chat should do first

1. Say explicitly: **"Courier Symphony"** so identity is confirmed.
2. Read/verify current repo state.
3. Read docs/V1_RULE_0.md if already merged; otherwise fetch it from the L1 rule branch.
4. Read GitHub Issue #54.
5. Check L1-L6 current status.
6. Continue the critical path. Do not restart architecture brainstorming.

If L2 is not active:
**activate Ledger implementation first.**

If Ledger/Golden Path is already green:
move to the next unproven gate, not back to planning.

## 12. Response style for the owner

- German unless asked otherwise.
- Direct, practical, copy/paste-ready.
- Clearly label MAC vs WINDOWS.
- For prompts: exact window/lane and exact paste count.
- Do not make the owner repeat context already present in this handoff/repo.
- When uncertain, verify current repo evidence instead of guessing.
- Avoid giving dozens of conflicting next steps.

---

## One-line bootstrap for a fresh chat

**Courier Symphony — continue the 2026-courier project from docs/NEXT_CHAT_HANDOFF.md + docs/V1_RULE_0.md + GitHub Issue #54; verify current integration/v1 state first, keep the Dennis+ChatGPT+Opus V1 architecture locked, and continue the shortest path Ledger -> Golden Path -> Desktop Hub -> Windows EXE.**
