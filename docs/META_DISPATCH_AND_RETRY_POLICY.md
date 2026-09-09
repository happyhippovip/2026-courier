# Meta Dispatch, Retry, Limit, and Operator Policy

## Purpose

Define how Courier decides whether to retry, wait, dismiss, escalate, ask for a human action, or dispatch work to one or more agents/computers without creating unnecessary prompt storms, conflicting edits, runaway work, or host overload.

This policy complements the host-safety and overheat resume-gate documents. Host safety and truth-first verification always outrank throughput.

## Core principle

**Idle capacity is not a reason to create work.**

Before every new dispatch, Courier must decide whether 0/3, 1/3, 2/3, or 3/3 agents should receive work.

The scheduler must optimize for correctness and low rework, not maximum simultaneous activity.

## Dispatch gate

Before issuing any prompt/job, evaluate in this order:

1. Is the current worktree/snapshot stable?
2. Is there already a single active code writer?
3. Would the new task touch the same files, state, process tree, test environment, account session, or output artifacts?
4. Is the task heavy or lightweight?
5. Would it compete with an active heavy job or exceed host duty-cycle/cooldown limits?
6. Does the task depend on another agent's unfinished result?
7. Can the work be done read-only/research-only without changing the shared state?
8. Is the next action a retry, a wait, a human gate, or a new dispatch?

If any dependency makes the answer unsafe or ambiguous, prefer **0/3 or 1/3** and wait.

## 0/3, 1/3, 2/3, 3/3 policy

### 0/3
Use when:
- worktree is changing during review;
- a writer is in the middle of a critical patch and other work depends on it;
- host resource guard/circuit breaker is open;
- a rate/usage limit requires waiting;
- task state is ambiguous;
- another result is expected imminently and would change the next instruction.

### 1/3
Use when:
- one writer must work alone;
- one bounded test/diagnostic is active;
- the next step is state-changing and must not race with another agent.

### 2/3
Use when:
- one agent is the single writer and the second is truly independent read-only research/review;
- tasks do not share mutable state or heavy-resource contention.

### 3/3
Use only when all three tasks are independent, bounded, non-conflicting, and safe under host/resource policy.

## Single-writer rule

Only one agent may modify the same production worktree at a time.

Reviewers and researchers must remain read-only while the writer is active.

A reviewer that detects a changing worktree must stop with `WORKTREE_CHANGED_DURING_REVIEW` rather than issue a mixed-snapshot verdict.

## Retry decision engine

Courier must classify failures before retrying.

### RETRY_IMMEDIATE
Allowed only for a clearly transient, low-risk failure with:
- no evidence of corrupted state;
- bounded retry count;
- no host/resource issue;
- no provider limit;
- no human gate.

### RETRY_BACKOFF
Use for transient service/network errors.
Requirements:
- exponential or bounded backoff;
- finite total attempts;
- no busy loop;
- state fingerprint must change or retry budget must decrease.

### WAIT_FOR_RESET_WINDOW
Use for legitimate provider usage/rate limits.
Courier must record the observed reset/availability evidence and wait rather than repeatedly retrying.

### HUMAN_ACTION_REQUIRED
Use for:
- login/authentication;
- CAPTCHA/2FA;
- billing/purchase;
- account verification;
- explicit approval gates;
- provider UI actions that the system cannot safely perform.

### DO_NOT_RETRY
Use when:
- deterministic verification says the effect is missing;
- identical state repeats beyond limit;
- resource guard/circuit breaker is open;
- cleanup/orphan state is unresolved;
- failure is permanent or policy-blocked.

## UI-action policy

Courier may reason about provider UI states such as:
- Retry
- Dismiss
- Continue
- Copy debug info
- Usage limit / wait window
- account attention required

But it must not click/trigger actions blindly.

Decision examples:
- transient error + safe state -> retry once within budget;
- same error repeats -> backoff or stop;
- usage limit -> wait for reset window;
- stuck diagnostic/debug view -> dismiss only if no active owned process depends on it;
- copy debug info -> only when needed for diagnosis and without exposing secrets unnecessarily;
- account/session problem -> central notification identifying which explicitly authorized account needs attention.

## Account and quota policy

Courier may manage explicitly authorized accounts as separate legitimate identities and may report which account currently needs attention or is unavailable.

Courier must **not** automatically rotate accounts, create accounts, or switch identities for the purpose of bypassing provider usage limits, rate limits, eligibility rules, or other service restrictions.

When an account reaches a legitimate usage limit, preferred behavior is:

`LIMIT_DETECTED -> RECORD -> WAIT/COOLDOWN -> NOTIFY CENTRAL -> RESUME WHEN ELIGIBLE`

If the human later chooses another explicitly authorized account for independent legitimate work, that selection must be explicit and auditable.

## Central status messages

Instead of producing prompt storms, Courier should surface concise operator messages, for example:

- `WAITING: Google Mac writer still active; Codex review blocked on stable snapshot.`
- `LIMIT: Account X reached provider window; next eligible time unknown/known.`
- `ACTION: Account X requires login/verification.`
- `RESOURCE_GUARD: heavy work paused for cooldown.`
- `RETRY_EXHAUSTED: task moved to BLOCKED.`
- `WORKTREE_CHANGED_DURING_REVIEW: rerun review after writer stops.`

## No pointless debug-output loop

`COPY_DEBUG_INFO` is never the default reaction.

Use debug capture only when it can answer a concrete diagnostic question. Do not repeatedly collect the same logs or dump large debug output into the central system.

Debug data must be bounded and sanitized for secrets.

## Progress / repeated-state guard

Before retrying or redispatching, compare a stable state fingerprint.

If there is no meaningful progress across the configured repeat threshold:

`COOLDOWN_REQUIRED` or `BLOCKED`

No infinite:

`retry -> same state -> retry -> same state`

## Host-safety integration

A retry or new dispatch is prohibited when:
- `RESOURCE_GUARD_OPEN`;
- `COOLDOWN_REQUIRED` for host load/duty cycle;
- an owned orphan remains;
- another heavy job is active;
- cumulative heavy-runtime budget is exhausted.

Human approval does not override these host-safety states.

## Canonical decision sequence

`OBSERVE -> CLASSIFY -> CHECK DEPENDENCIES -> CHECK HOST SAFETY -> CHECK LIMIT/HUMAN GATES -> CHOOSE 0/1/2/3 DISPATCH -> EXECUTE BOUNDED -> VERIFY -> RECONCILE`

If uncertain:

`WAIT / FAIL CLOSED / ASK FOR THE MINIMUM NECESSARY HUMAN ACTION`

## Permanent rule

Future Courier agents must read this policy before changing retry logic, multi-agent scheduling, account/session handling, UI-action automation, or central operator messaging.
