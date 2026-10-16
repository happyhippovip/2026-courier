# COURIER — 01 SHARED TRUTH

Status: SHARED TECHNICAL CONTEXT
Purpose: common architecture, current known anchors and non-negotiable invariants for all windows.

> Repository/runtime evidence wins if it conflicts with this file.
> Always verify current remote truth before acting.

---

# Repository

Public product repository:

```text
happyhippovip/2026-courier
```

Do not copy unreleased private strategy, pricing, moat analysis, community mechanics, consumer-interface details or private project-memory content into the public repo.

---

# Known starting anchors

These are **starting anchors**, not permission to skip verification.

```text
L2 known anchor:
703b523d1e7361a07c33303a1384d883df6660b0
PR #61

L3 canonical known anchor:
5f7e6b41e806cfe35f5c23beb4980aa44fe48cdf

L3/L4 composed bridge known anchor:
1a36b5024c3cae1a7c84a5008551aaaaa60b0c5e
PR #65

L4 canonical known anchor:
9ae63941840000d7a3be5d6838da0eeb389e61ca

L4 follow-up known anchor:
bbcff50a6280e141d759b52e28a2a06650549bd3
```

PR #65 is known to contain mixed lane ownership and must not be merged as-is unless the founder explicitly changes that instruction.

Before acting:

```text
git fetch --all --prune
```

Verify:
- remote heads;
- PR base/head;
- exact SHAs;
- exact-head CI;
- changed files.

---

# Locked V1 route

```text
ACTIVE LEDGER
->
RELIABLE AUTOMATION
->
GOLDEN PATH
->
DESKTOP HUB
->
WINDOWS EXE
->
CLEAN-MACHINE ACCEPTANCE
->
REAL ADAPTERS
->
DESKTOP ROBOT OVERLAY
```

Do not reorder this route for speculative work.

---

# Core architecture

- SQLite append-only journal
- deterministic projections
- one controller
- bounded workers
- independent verifier

**Conversation is NOT authority.**

Consequential state changes happen only through canonical actions/events.

---

# Golden lifecycle

```text
TASK_CREATED
->
TASK_CLAIMED
->
TASK_STARTED
->
RESULT_READY
->
RESULT_ACCEPTED
->
TASK_COMPLETE
->
shutdown
->
restart
->
deterministic replay to same final state
```

Failure gates include:
- worker crash;
- duplicate;
- stale result;
- late result;
- timeout;
- cancel;
- controller restart;
- corrupt/incomplete journal;
- uncertain non-idempotent outcome;
- resource failure.

No blind retry.

**SKIPPED != PASS.**

---

# Responsibility split

## L2 Controller

Chooses **WHAT**:
- adapter;
- params;
- effect_class;
- timeout;
- effect_key;
- consequence semantics.

## L3 Worker

Chooses **HOW** a trusted allowlisted adapter executes safely.

## L4 Verifier

Independently decides whether evidence proves success.

Do not make L2 invent arbitrary argv.

---

# Clean-split target

## L4 clean candidate

Canonical L4 plus only the minimal verifier-path change.

Expected L4-owned files:

```text
adapters/synthetic.py
tests/test_synthetic_adapter.py
```

## L3 clean candidate

Canonical L3 plus only the L3 execution bridge.

Expected L3-owned files:

```text
courier_worker/adapter_bridge.py
courier_worker/adapter_runner.py
courier_worker/host.py
courier_worker/service.py
tests/test_l3_worker_host.py
```

If L3 tests need the real synthetic adapter only for validation:
use a bounded **test-only** fake/stub when appropriate.

Do not copy L4 product code into L3.

Runtime may depend on the trusted L4 adapter being installed.

If required adapter code is absent:
**L3 must fail closed with SpecError.**

---

# Security invariants

Must preserve all of the following:

- no task-supplied argv;
- closed adapter allowlist;
- no arbitrary import;
- no arbitrary function selection;
- no arbitrary executable selection;
- no shell command derived from task input;
- malformed request fails closed;
- unknown adapter fails closed;
- missing adapter fails closed;
- no fake success.

Task input must not be able to select:
- module;
- function;
- executable;
- shell;
- runner implementation.

---

# Identity / idempotency invariants

Must preserve:

- task_id;
- attempt;
- dispatch_id;
- worker_id;
- effect_key verbatim.

`effect_key` must remain present in the trusted runner request.

Synthetic may not consume effect_key externally.

That is **not** permission to remove it.

Future consequential adapters will need the same stable key for provider-side idempotency.

---

# Containment invariants

Must preserve:

- timeout containment;
- lease containment;
- cancel containment;
- durable outbox;
- controller remains sole journal writer.

No unbounded subprocesses.
No unbounded polling.
No retry storms.

On Mac:

```text
MAX_HEAVY_JOBS = 1
```

Resource `UNKNOWN` is not healthy.

If:

```text
EMFILE
Too many open files
os error 24
```

then:

```text
RESOURCE_PAUSE
NO RETRY
```

Do not dismiss process-tree or zombie failures as “environment-only” until native target-platform evidence exists.

---

# Evidence discipline

Separate every claim into one of:

- SOURCE_INSPECTION
- LOCAL_TEST
- NATIVE_PLATFORM_TEST
- EXACT_HEAD_CI
- SELF_REPORTED_ONLY

Never promote SELF_REPORTED_ONLY to PASS.

Never transfer PASS from one SHA to another.

Never infer Windows from macOS/Linux/container behavior.

Never infer Linux from macOS.

Never call a skipped test passed.

---

# Failure diagnosis order

For a failing test, classify first:

```text
EXPECTED
TEST_HARNESS_DEFECT
PLATFORM_SEMANTICS
PRODUCT_DEFECT
WRONG_COMPOSITION
WRONG_SHA
STALE_WORKTREE
SECURITY_ISSUE
RESOURCE_ISSUE
```

Find the first causal failure.

Do not patch downstream symptoms.

---

# Final integration questions

Before `READY_FOR_L1_INTEGRATION=YES`, establish:

1. L2 product code unchanged.
2. L3 ownership clean.
3. L4 ownership clean.
4. Task input cannot supply argv.
5. Task input cannot choose arbitrary executable/module/function.
6. Unknown adapter fails closed.
7. Missing adapter fails closed.
8. effect_key preserved verbatim.
9. effect_key present in trusted runner envelope.
10. Cross-dispatch evidence rejected.
11. Exit-0 without structured report cannot become success.
12. timeout/cancel/lease containment preserved.
13. controller remains sole journal writer.
14. intended Golden suite actually ran.
15. Golden skips = 0.
16. native Windows containment proven on exact candidate.
17. POSIX/macOS/Linux evidence kept distinct.
18. CI claims tied to exact candidate SHA.
19. no PASS depends only on an agent report.
20. no unresolved causal blocker remains.

---

# Product truth that must not be broken by technical fixes

Courier customer-facing states may later project as:

```text
NEEDS YOU
WORKING
DONE
```

But technical implementation must preserve the underlying truth:
- uncertainty remains visible;
- human-confirmed completion is not the same as verifier-confirmed completion;
- a cancelled uncertain external effect is not falsely shown as “nothing happened”;
- consequential ambiguity goes to an attributable human decision;
- duplicate consequence is not accepted as normal.

Technical fixes must strengthen, not weaken, those guarantees.

---

# Stop condition

A window should stop only when:
- its assigned gate is proved;
- its assigned gate is disproved;
- or it reaches a genuine access/ownership/causal blocker.

Do not stop merely because one subtest failed if other useful investigation remains possible.
