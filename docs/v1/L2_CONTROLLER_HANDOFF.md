# L2 controller: contracts for the other lanes

Lane L2 owns `courier_core` (journal, state machine, controller, `/v1` API).
This page lists what the final hardening pass added and exactly what other
lanes must do with it. The binding API surface is still `tests/golden/README.md`;
everything here extends it, nothing in it changed.

## 1. Fail-safe effect class (done in L2)

- Intake accepts `effect_class` ∈ {`idempotent`, `non_idempotent`}; anything else is `400`.
- Retry decisions use a whitelist (`state_machine.may_auto_retry`): only
  `idempotent` is retried automatically. Any other class, including a
  future one added to the intake list without touching the decision code,
  fails closed: a started attempt with an unknown outcome is `BLOCKED`.
- A cancel request never outranks that uncertainty.
- A worker failure that does not say `retryable` is retryable only for
  `idempotent` tasks.

**L3 (worker host):** for a non-idempotent task, send `"retryable": true` with
`outcome: "failure"` only when the external effect certainly did not happen.

## 2. Human Desk decisions (done in L2; L5 builds the UI)

A `BLOCKED` task leaves `BLOCKED` only through a human decision that names an actor:

```
POST /v1/tasks/<id>/resolve
{"decision": "effect_confirmed" | "retry_authorized" | "cancel",
 "actor": "<who decided, 1..200 chars>",
 "attempt": <the blocked attempt, from GET /v1/tasks/<id>>,
 "reason": "<why, 1..2000 chars>"}
```

| decision | journal event | result |
|---|---|---|
| `effect_confirmed` | `EFFECT_CONFIRMED` | `COMPLETE`, `resolution = "effect_confirmed"`, nothing is re-executed, `accepted_result_id` stays null |
| `retry_authorized` | `RETRY_AUTHORIZED` | `QUEUED` for exactly one fresh, fenced attempt, even if the budget is spent (`max_attempts` becomes `attempt + 1`); refused while a cancel is pending |
| `cancel` | `TASK_CANCEL_REQUESTED` + `TASK_CANCELLED` (both carry `actor`) | `CANCELLED`, `resolution = "cancelled_effect_unknown"` |

- **Answers:**
  - `200 {"status", "decision", "duplicate"}`. Repeating the same decision returns `duplicate: true`.
  - `409 decision_conflict`: a different decision for an attempt that was already decided.
  - `409 stale_decision`: the request names an old attempt; the answer carries the current `attempt`.
  - `409 not_blocked`, `409 cancel_requested`, `400`, `404`.
- `POST /v1/tasks/<id>/cancel` on a `BLOCKED` task now needs `{"actor"[, "reason"]}`. Without an actor it answers `409 actor_required`.
- **Projection fields:**
  - `resolution` is one of `verified`, `effect_confirmed`, `cancelled_effect_unknown` or null.
  - `decided_by` is the actor of the last human decision.
  - The UI must show `effect_confirmed` as "confirmed by a person", never as verified.
- **Evidence for the desk:** a result reported by a superseded dispatch is journaled as `LATE_RESULT_DISCARDED` with its `outcome`, `artifacts`, `reported_reason` and `attempt`. It never changes the task.
- The actor is asserted by the authenticated local client (one per-install token). L5 decides how a person is identified; L2 records it durably.

## 3. Build and verifier identity (done in L2; L6 sets the build id)

- **`CONTROLLER_STARTED.payload.build`** contains:
  - `version`
  - `build_id` (from `COURIER_BUILD_ID`)
  - `source_sha256` (of `courier_core/*.py`; null in a frozen build)
  - `python`

  `GET /v1/health` returns the same object. Every event belongs to the build of the nearest preceding `CONTROLLER_STARTED`; use `courier_core.build.build_for_seq`.
- **`RESULT_ACCEPTED` / `RESULT_REJECTED.payload.verifier`** is one of:
  - `{"kind": "adapter", "name", "version", "source_sha256"}`, where `version` is the adapter module's optional `VERIFIER_VERSION`;
  - `{"kind": "courier_rule", "name", "adapter"}`, for the fail-closed rules.
- Attribution lives only in event payloads and system events, so `projection_hash` does not depend on it.

**L6:** set `COURIER_BUILD_ID` (for example the release tag plus commit) in the packaged launcher's environment.

**L4:** set `VERIFIER_VERSION = "<n>"` in each adapter module and bump it when its acceptance rules change.

## 4. Stable effect key (done in L2; L3/L4 pass it through)

- `spec.effect_key` in the `POST /v1/claim` answer (and `effect_key` in `GET /v1/tasks/<id>`) is `cfx-` followed by 40 hex characters, derived from `task_id` alone.
- It is identical for every attempt of a task: automatic retries, retries after a restart and human-authorized retries. A repeated `idempotency_key` maps to the same task and therefore the same effect key.

**L3:** hand `spec.effect_key` to the adapter unchanged.

**L4 / real adapters:** send it as the provider's idempotency key (for one task with several external effects, use `<effect_key>:<n>` with a fixed `n`), so a provider refuses a second copy of an effect whose completion Courier could not observe.

## 5. Projection version

- `PROJECTION_VERSION` is now 2 (`resolution`, `decided_by`).
- **Opening a journal with an older projection:** the projection is rebuilt from the verified event chain in one transaction. Events are never touched.
- **A damaged journal:** it stays read-only. Task reads then answer `503` if its projection predates this build.
