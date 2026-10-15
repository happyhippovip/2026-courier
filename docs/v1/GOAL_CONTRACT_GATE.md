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

`ChiefCommander.formulate_workflow_plan` returns no steps unless `$COURIER_HOME/goal_contracts.jsonl` already holds a confirmed contract that accepts the idea. That is the file `Controller.confirm_goal` appends. If `COURIER_HOME` is unset or empty, the chief stays blocked (fail closed), even when `goal_contracts.jsonl` is sitting in the repo root. The name is gitignored, so that root file is not the store by itself. If `COURIER_HOME` points at the repo, the file is read. `Path.resolve` follows symlinks, so a `COURIER_HOME` that is a symlink to the repo is the same: the file at the repo is read. An empty plan makes `execute_human_idea` return `BLOCKED_GOAL_CONTRACT`.

`server/app.py` is not edited. When the chief returns no steps, that process answers 503 `planner returned no actionable tasks`. That text does not say a goal contract blocked the plan, so the 503 is misleading in this case.

The ledger bridge copies the five task-view fields onto the posted task. Its `--home` is its own required argument. It is not `COURIER_HOME`, and nothing checks that it is the directory the controller was started with. Before posting, the bridge runs `validate_task` on `<its --home>/goal_contracts.jsonl`. The controller, on `POST /v1/tasks`, runs `validate_task` on its own home.

When those directories differ, the two checks stay separate:

- The bridge file does not accept the spec: the bridge parks the mission and does not post. A contract that exists only in the controller's home does not let it through.
- The bridge file accepts the spec: the bridge posts. The controller then checks its own file. Any answer other than 200 or 201, including 409 when the controller's file does not accept the task, is recorded as `skipped` / `rejected`. The mission stays unposted and the next run tries the post again. It is not parked by the bridge's pre-check.
- The bridge also sends the token from `<its --home>/run/controller.token`. If that token is not the controller's token, the post is 401 and is recorded the same way, before the controller's goal check.

Specs that post through that bridge, including the verified A-to-B input handoff, need the same five fields or whichever of those two checks runs will refuse the post.

## Tasks left QUEUED

`Controller.claim` skips a queued task that `validate_task` does not accept. It writes no status and no reason. The task stays `QUEUED` forever. That includes a legacy task journaled with no goal contract. A new create without an accepted contract is refused before the journal; the skip applies only to tasks already queued.

## OPEN: direct `server/app.py` path

`server/app.py` is not edited. A `workflow_plan` posted directly to `POST /goals`, and `POST /tasks/claim` on that process, never reach this controller. Those tasks are not covered by this gate. The 503 `planner returned no actionable tasks` on the planner path is the same misleading answer described above.

**OPEN — awaiting Dennis decision.** Whether that process should call the controller, refuse those routes, or stay as it is.

## OPEN: R1, unkeyed store

Anyone with shell or file access to `$COURIER_HOME` can hand-write a confirmation that the chief and the controller accept. Each stored line carries `sha256` of its own contract JSON, and the read accepts the line when that digest matches. The digest is an unkeyed sha256, so it detects a body that does not match its hash. It does not show who wrote the line. The same file is read when `COURIER_HOME` points at the repo or is a symlink that resolves to the repo.

The confirm route does not offer this write. `POST /v1/goals/confirm` still requires the human-confirm token, and the controller does not invent a confirmation.

**OPEN — R1.** Proposed follow-up: HMAC-keyed records. That is a separate pull request with its own criteria.
