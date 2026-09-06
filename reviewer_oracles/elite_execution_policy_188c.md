# Elite Execution Policy Contract — 188C

Status: reviewer-owned integration contract for a future Mission 189.  This
document does not activate, dispatch, or mutate the current runtime.

## 1. Required action contract

Every action considered for non-local judgment must have an immutable,
machine-readable `EliteActionContract` containing exactly these required
fields:

`GOAL`, `EXPECTED_UNLOCK`, `QUALITY_FLOOR`, `RISK_CLASS`,
`NEW_INFORMATION`, `WHY_MODEL`, `WHY_NOT_LOCAL`, `WHY_NOT_CACHE`, `WHY_NOW`,
`DEPENDENCIES`, `MUTATION_SCOPE`, `OPPORTUNITY_COST`, `CONTEXT_REFERENCE`,
`EXPECTED_INFORMATION_GAIN`, and `STOP_CONDITION`.

Absent, empty, or contradictory mandatory fields fail closed to
`UNKNOWN_REQUIRES_CLASSIFICATION`; they never justify a model invocation.
`MUTATION_SCOPE` is advisory only until ordinary scope locks and human gates
have independently admitted the action.

## 2. Intelligence ladder and quality floor

Use the first tier that can meet the declared quality floor:

1. cached accepted judgment with a still-valid semantic fingerprint;
2. local deterministic validation, hashes, parsing, or tests;
3. existing structured evidence and result barriers;
4. one targeted low-cost model judgment;
5. a stronger model only when tier 4 cannot meet the floor;
6. an independent second judgment only when the risk class requires it;
7. a human gate for MONEY, PUBLICATION, IDENTITY_LEGAL, and other real
   account decisions.

Quality floors are: `LOW` = deterministic evidence and bounded scope;
`MEDIUM` = targeted tests plus affected-source evidence; `HIGH` and
`SECURITY` = fail-closed validation and independent review; `MONEY`,
`PUBLICATION`, and `IDENTITY_LEGAL` = the applicable technical floor plus an
unbypassed human decision.  A cheaper provider never lowers a quality floor.

## 3. Semantic change and decision validity

The semantic detector returns exactly one of:

- `NO_RELEVANT_CHANGE`
- `RELEVANT_LOW_RISK_DELTA`
- `RELEVANT_DECISION_DELTA`
- `RELEVANT_HIGH_RISK_DELTA`
- `UNKNOWN_REQUIRES_CLASSIFICATION`

It compares canonical input hashes, dependency identifiers, policy revision,
risk class, affected paths, and decision-relevant structured fields.  A
format-only change or an unrelated path is `NO_RELEVANT_CHANGE`; a
security-relevant path is `RELEVANT_HIGH_RISK_DELTA`.  Unknown or malformed
evidence fails closed.

Accepted decisions are not refreshed merely because time passed.  Their state
is `VALID`, `INVALIDATED_BY_RELEVANT_DELTA`, `INVALIDATED_BY_POLICY_CHANGE`,
`INVALIDATED_BY_DEPENDENCY_CHANGE`, or `UNKNOWN_REQUIRES_CLASSIFICATION`.
Only `VALID` permits cache reuse.

## 4. Scheduling and wake policy

Speculative local preparation is permitted while a model is pending only when
it is reversible, does not assume the pending answer, does not mutate a shared
scope, and can be discarded without consequence.  It cannot create another
model request.

An idle system wakes only on new evidence, a satisfied result barrier, a
valid human decision, a dependency-state transition, or an explicit bounded
schedule event.  It does not poll a model to discover work.

The opportunity-cost gate returns exactly one of `RUN_NOW`,
`DEFER_FOR_HIGHER_VALUE`, `LOCALIZE`, `COALESCE`, `WAIT_FOR_DEPENDENCY`, or
`DROP_ZERO_GAIN`.  It compares expected unlock, information gain, quality
floor, resource contention, active human gates, and higher-value ready work.
Blocked MONEY or HUMAN branches never block safe independent READY work.

The scheduler races to the first *validated useful state*, not the first
output.  It stops when the declared quality floor and stop condition are met;
it must not start a perfection loop.  Identical results are deduped and
compatible independent results are coalesced before another judgment.

## 5. Capability, context, and anti-swarm policy

Route by required capability, quality floor, access state, mutation scope, and
current provider capacity.  Registered agent names alone are not execution
evidence.  Capability unavailability yields `LOCALIZE`, `WAIT_FOR_DEPENDENCY`,
or a human gate; it never silently bypasses a safety constraint.

Pass a stable `CONTEXT_REFERENCE` plus the relevant delta, not repeated full
history.  Context reuse is valid only while its semantic fingerprint remains
`VALID`.

One logical work item may have many registered roles but at most one necessary
model judgment at a time.  Workers may emit structured evidence but cannot
fan out shadow model calls.  Result barriers, scope locks, cache reuse, and
the opportunity-cost gate jointly enforce this anti-swarm rule.

## 6. Negative-work accounting and quality-adjusted amplification

Persist separately: calls avoided by cache, calls avoided by local resolution,
zero-gain drops, coalesced decisions, correct waits, blocked unsafe actions,
context bytes avoided, duplicate results ignored, and model calls actually
executed.  These counters are evidence, not a goal to maximize.

The quality-adjusted useful-state metric counts a transition only when the
declared quality floor was met, the transition has new validated evidence or a
real unlock, and no human/safety gate was bypassed.  Repeated reviews, status
chatter, and low-quality outputs add zero.  The system is not allowed to game
the metric by lowering a floor, splitting one judgment into many agents, or
calling a model without a positive expected information gain.

## 7. Minimal Mission 189 integration boundary

Add a pure contract validator and semantic-fingerprint classifier at the
existing model-admission boundary in `scripts/autonomy_control_plane.py`.
Persist the contract fingerprint, dependency identifiers, policy revision, and
decision-validity state alongside accepted judgments.  Add an opportunity-cost
evaluator before admission and emit deterministic wake events from existing
barriers/dependency changes.  Reuse existing circuit-breaker, scope-lock,
cache, capability, and spend/human-gate controls; do not create a second
scheduler or a new model dispatch path.
