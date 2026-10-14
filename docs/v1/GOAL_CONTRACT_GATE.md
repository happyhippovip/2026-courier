# Goal-contract gate

A task is journaled and claimable only when a stored, human-confirmed goal contract accepts it. `courier_core/goal_contract.py` drafts, confirms, stores, and validates. `Controller.create_task` and `Controller.claim` always call `validate_task`. There is no adapter-intake exemption: a task with no `goal` member is still checked.

## Task view

Every dispatch carries these five fields:

| Field | Meaning |
| --- | --- |
| `goal_id` | Which stored contract the task claims |
| `goal_fingerprint` | sha256 of the terms, excluding confirmations |
| `scope` | Paths or units the task may touch |
| `acceptance_ids` | Which acceptance criteria this task claims |
| `evidence_class` | How the result will be checked |

`validate_task` returns `ACCEPTED` only when the latest stored contract for that `goal_id` is human-confirmed, the fingerprint matches, the scope stays inside the allowed set, the acceptance ids exist on the contract, and the evidence class matches. Otherwise the controller answers `409` and does not journal the task:

- `NOT_VERIFIABLE` / `missing_contract` — no stored contract, or the task view is incomplete
- `HUMAN_CONFIRMATION_REQUIRED` — the contract is unconfirmed, or the task widens scope (`scope_widened`)
- `REVALIDATION_REQUIRED` / `stale_fingerprint` — the task is bound to an older fingerprint

## Draft and confirmation

Free text drafts an unconfirmed contract (`outcome: DRAFTED`, `confirmed: false`, `dispatched: false`) and is not stored. `NEEDS_CLARIFICATION` is only a missing or contradictory goal. A single "or" or "either" is not one of those.

`POST /v1/goals/confirm` stores a draft only after a dedicated human proof:

- The secret is `COURIER_HUMAN_CONFIRM_TOKEN` in the environment. It is never committed.
- The caller presents it in `X-Courier-Human-Token`.
- The shared worker and bridge token (`X-Courier-Token`) is not this secret. If the two values are the same, confirmation fails closed.
- The JSON field `authenticated` is ignored.
- `actor_ref` must be a human identity. `anonymous` and anything starting with `agent:` are refused.
- `GoalContractStore.append` accepts confirmed contracts only. The controller never invents a confirmation.

An agent that holds `X-Courier-Token`, sets `actor_ref` to `person:x`, and sets `authenticated` to true is rejected. Nothing is appended.

## Callers that must present the task view

`ChiefCommander.formulate_workflow_plan` returns no steps unless the store already holds a confirmed contract that accepts the idea. An empty plan makes `execute_human_idea` return `BLOCKED_GOAL_CONTRACT`.

The ledger bridge copies the five task-view fields onto the posted task and parks the mission before claim when `validate_task` would reject the spec. Specs that post through that bridge, including the verified A-to-B input handoff, need the same five fields or the controller refuses the post.

## OPEN: direct `server/app.py` path

`server/app.py` is not edited. A `workflow_plan` posted directly to `POST /goals`, and `POST /tasks/claim` on that process, never reach this controller. Those tasks are not covered by this gate.

**OPEN — awaiting Dennis decision.** Whether that process should call the controller, refuse those routes, or stay as it is.
