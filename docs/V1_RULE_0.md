# RULE 0.000000000 — Finish Courier

Status: **AUTHORITATIVE PRODUCT NORTH STAR FOR V1**

This document exists so a new chat, agent, contributor, reviewer, or future maintainer can understand the point of Courier without reconstructing months of orchestration history.

## The goal

Ship a real Windows application that people can install and use.

The target is not another permanent swarm experiment, another planning document, another night queue, or another collection of half-integrated branches.

The target is:

**A finished Courier Windows application, distributed as an EXE/installer, whose runtime is reliable, whose ledger is actually the source of truth, whose automation works end-to-end, and whose local product experience creates enough measurable value that users want to keep using it and voluntarily replenish credits when paid capability is useful.**

Credits are a budget/control mechanism for valuable capability. They are **not** a promise of profit, guaranteed returns, or literally zero total operating cost.

## What the application should do for users

Courier should reduce repeated computer work instead of creating more work.

Core value includes:

- reliably carrying tasks from creation through execution, verification, result, and completion;
- automatically organizing user-selected local files/data where the user has explicitly enabled that behavior;
- reducing repetitive daily sorting and housekeeping;
- preserving clear evidence of what happened;
- recovering after crashes/restarts without silently duplicating work;
- providing local diagnostics and replay;
- keeping the default local path low-cost and avoiding unnecessary external/API spend;
- making optional paid/credit-backed capabilities visibly worth their cost.

Local-first means:
- no secret or private file upload merely because Courier can access it;
- explicit user-selected scopes;
- no external action without the product contract/permission that authorizes it;
- the app should remain useful even when optional external providers are unavailable.

## Ledger rule

The Ledger is no longer a slogan or a side feature.

For V1 it must become the active runtime truth:

**SQLite append-only event journal -> deterministic projection -> controller -> worker -> verifier -> UI.**

No major new product work outranks activating and proving this path.

The V1 Golden Path must be real:

TASK_CREATED
-> TASK_CLAIMED
-> TASK_STARTED
-> RESULT_READY
-> RESULT_ACCEPTED
-> TASK_COMPLETE
-> shutdown
-> restart
-> deterministic replay to the same final state

Failure tests must cover at least:
- worker crash
- duplicate result
- late/stale result
- timeout
- cancellation
- controller restart
- corrupt/incomplete journal detection
- non-idempotent uncertain outcome -> BLOCKED, not blind retry

Until this works, do not describe Courier as autonomously finished.

## Product runtime rule

The development swarm is not the product.

The shipped product must not depend on dozens of manually opened AI windows.

V1 runtime target:
- one controller;
- bounded worker hosts;
- one canonical verifier path;
- one canonical ledger;
- deterministic replay;
- bounded processes/descriptors;
- clean shutdown and restart recovery.

## Resource rule

The prior EMFILE / process-exhaustion class must be designed out.

Use:
- bounded concurrency;
- explicit process and descriptor budgets;
- timeout -> kill tree -> reap;
- file-backed child output where appropriate;
- rotating logs;
- backpressure;
- health gates;
- no uncontrolled watchers;
- no unbounded helper spawning.

Do not treat raising the OS file-descriptor limit as the main fix.

## Windows V1 rule

The internal V1 finish line is a Windows 11 clean-machine acceptance run:

1. Install Courier without Python already installed.
2. Start the app.
3. Ledger/controller report normal health.
4. Run the synthetic Golden Task.
5. Show the real lifecycle in the UI.
6. Complete exactly once.
7. Close Courier and leave no orphan Courier processes.
8. Reopen Courier.
9. Reconstruct the same state from the ledger.
10. Replay the run deterministically.
11. Produce a diagnostics bundle with no leaked secrets.
12. Uninstall program files while preserving user data unless the user explicitly chooses removal.

Packaging baseline:
- PyInstaller onedir;
- per-user Inno Setup installer;
- local application data under %LOCALAPPDATA%\Courier;
- unsigned internal V1 is acceptable until external distribution requires signing.

## Desktop identity rule

Courier should remain distinctive.

The Courier / package / customs / result / retry / human-desk metaphor is part of the product identity.

V1 may begin with robots inside the Courier Hub window.

The robots must visualize **real ledger/runtime state**, not fake busy motion.

Later stages may add a transparent desktop overlay and window-anchored movement, but those stages must reuse the same journal-driven truth and must never become a second orchestrator.

## Credit/value rule

The commercial aspiration is simple:

Users should want to replenish credits because Courier saves or creates enough measurable value that the optional paid capability feels worth replenishing.

Design implications:
- local deterministic work should not consume paid model/API capacity unnecessarily;
- expensive provider calls must be purposeful and visible;
- show users what credits funded;
- measure useful outcomes, time saved, completed work, and avoided repetition;
- never burn credits just to make the system look active.

Do not claim guaranteed financial profit.

## Priority rule

When two tasks compete, prefer the one that shortens the path to this sequence:

**active ledger -> reliable automation -> Golden Path -> Desktop Hub -> Windows EXE -> clean-machine acceptance -> real adapters -> desktop robot overlay.**

A new feature that does not shorten or de-risk that route is deferred.

## V1 writer rule

Until the internal EXE passes acceptance, the only implementation lanes are:

- L1 Integration / CI / Golden Harness
- L2 Journal / Controller / API
- L3 Bounded Worker Host
- L4 Verifier / Synthetic Adapter
- L5 Desktop Hub / Replay
- L6 Packaging / Launcher / Diagnostics

Everything else is read-only, review, evidence, or deferred unless Dennis explicitly changes this rule.

## No architecture churn

The Dennis + ChatGPT + Opus Final Reconciliation is the V1 architecture baseline.

Do not reopen the whole architecture because a new agent prefers a different framework.

Change the contract only when current implementation evidence proves a specific problem.

When changing it, record:
- exact contradiction;
- smallest required adjustment;
- affected Golden Test;
- why the original invariant could not be preserved.

## Rule for new chats and new agents

Read this file first.

Then read the current V1 integration status and the canonical continuity issue.

Do not restart the project from historical prompts.

Do not reactivate retired 30x/100x/NIGHT/YOLO writer swarms.

Do not invent a new product destination.

The destination is already defined:

**Finish the reliable ledger-backed Courier runtime and ship the Windows application.**

## Definition of "finished enough to move on"

V1 is ready to lift the freeze only when:

- Golden happy path is green;
- required failure injections are green;
- journal replay is deterministic;
- no runtime state depends on git;
- controller restart is safe;
- worker cleanup is safe;
- clean Windows 11 install succeeds;
- Courier closes without orphan processes;
- restart reproduces the same final state;
- diagnostics are usable and redact secrets;
- the internal Windows installer artifact exists and passes acceptance.

After that:
- choose the first real provider adapter;
- then build the real desktop overlay;
- then broaden integrations and product polish.

---

**RULE 0.000000000: FINISH THE PRODUCT.**

Every plan, branch, agent, prompt, test, and feature exists to move Courier closer to a reliable installable application people can actually use.
