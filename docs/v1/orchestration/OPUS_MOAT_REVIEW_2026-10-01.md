# Opus Strategic Moat Review — Harvest 2026-10-01

Status: **ADVISORY REVIEW HARVEST**

Source: Opus Strategic Moat / Anti-Commodity review supplied by the owner on 2026-10-01.

Current repo facts re-verified before this harvest:
- `integration/v1`: `5dea6473`
- `lane/L2-controller`: `fc4c279a`
- L2 is present remotely but not integrated into `integration/v1`
- no open L2-controller PR was found at harvest time

## Core correction

The append-only ledger by itself is not a durable moat.

Durable-execution/checkpointing infrastructure is becoming commodity for developers.

Courier's stronger product-level differentiation is:

**consequence semantics + verified completion + uncertainty reconciliation + replayable/explainable customer truth**

The ledger is the foundation that makes those guarantees enforceable; it is not sufficient as the headline differentiator by itself.

## Preserve-now findings

The Opus review identified four concrete V1-compatible or near-V1-compatible boundaries worth preserving.

### 1. Fail-safe effect-class default

Current/future decision logic must never assume a newly introduced effect class is retry-safe.

Policy:

```
only explicitly idempotent effects are auto-retryable
everything else defaults to uncertain/consequential
```

A future class such as `physical`, `medical`, `flight`, or another consequential effect must therefore fail closed unless a stricter profile explicitly proves retry safety.

Owner: L2

Acceptance:
- unknown effect class does not auto-retry;
- it transitions to BLOCKED/uncertain handling according to the controller contract.

### 2. Human Desk decision events with actor identity

BLOCKED must not become a customer dead end.

The journal/state-machine contract should support explicit human reconciliation outcomes such as:

- effect confirmed -> accept/complete;
- retry authorized -> create/allow a new fenced attempt;
- cancel.

Every consequential human decision should carry durable actor identity.

Owner:
- L2 for events/state-machine/API
- L5 later for customer UI

Preserve-now requirement:
do not build a Human Desk UI around ad-hoc state mutation.

### 3. Build/verifier identity in durable truth

Later assurance and change-control depend on knowing which software/verifier made a consequential decision.

Preserve-now target:
- controller/build identity in controller-start metadata;
- verifier identity/version in acceptance/verdict metadata;
- schema/config identity where cheap and stable.

Owner:
- L2 / L4

Do not turn this into a large provenance framework before EXE.

### 4. Stable effect key before real adapters

Exactly-once recording inside the ledger does not automatically guarantee an external provider effect happened only once.

Before REAL ADAPTERS, Courier should have a stable effect/idempotency key contract that can be passed to providers that support one.

Owner:
- L2 contract
- L4 adapter/verifier contract

Timing:
after EXE if necessary, but before consequential real adapters.

## Product advantage experiments

The review's most valuable experiments are:

1. **Proof-of-done receipt**
   - derived only from ledger/projection/evidence;
   - reproducible after restart;
   - shows request, attempts, evidence hash, verifier result, retries/reconciliation.

2. **Human Desk reconciliation**
   - prove BLOCKED is recoverable without hidden mutation;
   - actor + decision event + deterministic replay.

3. **Crash-proof acceptance demo**
   - kill controller/worker mid-task;
   - prove exactly-once completion and deterministic replay on a clean Windows machine.

4. **Babysitting/cost metric**
   - verified completions;
   - automatic recoveries;
   - human interventions;
   - wasted retries;
   - later compute cost per verified result.

5. **Stable effect key**
   - provider double demonstrates one external effect under replay/retry.

## Anti-commodity rules

Protect these boundaries:

1. The journal is the only authoritative truth.
2. Effect semantics fail safe.
3. The verifier stays fail closed.
4. Transition rules stay centralized.
5. Human/machine decisions are attributable.
6. Providers remain adapters, not kernel truth.
7. Replay explains customer-visible state.
8. Corruption/degraded mode never silently repairs history.
9. Value is measured in verified useful work and reduced intervention, not agent activity.
10. Domain profiles tighten the kernel; they do not fork it.

## Scope

This harvest does **not** change the locked route:

ACTIVE LEDGER
-> RELIABLE AUTOMATION
-> GOLDEN PATH
-> DESKTOP HUB
-> WINDOWS EXE
-> CLEAN-MACHINE ACCEPTANCE
-> REAL ADAPTERS
-> DESKTOP ROBOT OVERLAY

The review is useful precisely because the strongest findings can be preserved without turning V1 into a speculative platform rewrite.
