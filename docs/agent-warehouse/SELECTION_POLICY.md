# Courier Symphony — Agent Selection Policy

Status: bootstrap policy for Issue #120.

## Objective

Select the safest, cheapest, already-authorized capable owner without creating duplicate work or unnecessary provider spend.

## Decision order

1. **Task / gate fit** — what exact capability is required now?
2. **Ownership** — is another writer already mutating the same logical scope?
3. **Host / OS** — does the evidence require Windows, macOS, Linux, browser, GPU, or local-only execution?
4. **Authority / side effect** — does the task require a human gate, external publication, secrets, destructive action, or spend?
5. **Cost** — among capable authorized options, prefer the cheapest/included option per Issue #118.
6. **Availability** — use provider continuity state from Issue #119.
7. **Reasoning effort** — use the lowest reasoning effort likely to succeed.
8. **Reserve** — use a Bodyguard only if the normal specialist is unavailable and the capability match is explicit.

## Default provider/task fit

These are routing defaults, not immutable assignments.

### Muse

Prefer for:
- bounded verification;
- focused repository inspection;
- small distinct implementation units;
- unattended read/verify/scout work on the proven Mac runner path.

Do not use a Muse swarm. On constrained Mac hardware, one heavy Muse execution at a time.

### Google Antigravity / Gemini

Prefer for:
- primary implementation when scope is free;
- cross-file product work;
- Windows implementation when running on real Windows;
- macOS/cross-platform implementation when running on Mac;
- visual or browser-adjacent work when its capability is actually available.

### Codex

Prefer for:
- high-information-gain debugging;
- hard root cause;
- architecture contradiction;
- adversarial verification;
- process/recovery/idempotency analysis;
- targeted repair when that is the shortest path.

Do not spend Codex on routine duplicate review.

### Claude

Until a first-class bridge and capability evidence exist, treat Claude as an external/manual provider path, not as a fully integrated Courier runtime agent.

When integrated, prefer for:
- deep coherent multi-file implementation;
- long-context review;
- difficult integration in a distinct scope.

### Bodyguards

Reserve only.

Use when:
- normal specialist is unavailable;
- required capability is in the proven Bodyguard capability set;
- assignment will not duplicate another mutable writer.

STANDBY means no model work.

## Reasoning effort

Use the lowest level likely to succeed.

- LOW: status, deterministic transforms, simple repo inspection, straightforward verification.
- MEDIUM: normal implementation, integration, multi-file reasoning.
- HIGH: difficult root cause, ambiguous architecture, adversarial verification, complex recovery.
- HIGHEST/PRO: only with concrete evidence that lower levels are insufficient or when task class clearly requires it.

If a more expensive model/reasoning level is chosen while a cheaper capable option exists, record the escalation reason.

## Continuity

When a provider becomes unavailable:

1. checkpoint branch/SHA/PR/workkey/mutable scope/evidence/next action;
2. continue LOCAL_READY work if available;
3. use only a safe authorized capability-matching fallback;
4. otherwise hibernate;
5. on reset, perform one bounded recovery probe;
6. refetch current repository truth;
7. reconcile ownership;
8. resume the same logical work without repeating proven units.

See Issue #119.

## Do not create new agents casually

A new runtime agent requires evidence that:

- the responsibility is repeated and durable;
- no existing owner can absorb it cleanly;
- capability can be declared and tested;
- authority and side effects can be bounded;
- the new agent reduces complexity rather than adding another overlapping worker.

Prefer extending existing routers/stewards/bridges.

## Operator-facing selection record

For every non-trivial dispatch, Courier should be able to expose:

- TASK / WORKKEY
- REQUIRED_CAPABILITY
- SELECTED_AGENT
- SELECTED_PROVIDER
- MODEL / REASONING
- HOST
- MUTABLE_SCOPE
- DUPLICATE_CHECK
- COST_CLASS
- CHEAPER_CAPABLE_OPTION
- ESCALATION_REASON
- FALLBACK
- CONTINUITY_STATE

Dennis should not need to memorize the warehouse.
