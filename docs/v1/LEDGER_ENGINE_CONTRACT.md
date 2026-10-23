# Ledger engine contract (for A→B→C integrators)

`courier_runtime/ledger_engine.py` joins the journal controller (one task) and Kirby (which workkey is next).
It changes neither: `courier_core/controller.py` and `courier_runtime/continuity.py` stay as they are.

| Step | Call | Guarantee |
|---|---|---|
| QUEUE | `engine.add_workkeys([...])`, `engine.open_slot(slot, provider)` | Written under the campaign file lock |
| CLAIM | `engine.next(slot)` → `(workkey, token)` or `None` | One owner per workkey across processes; a slot that still owns a workkey gets it back |
| COST GATE | `engine.submit(workkey, task_body)` → `task_id` | `params.estimated_cost_eur` must be a finite number ≤ spend limit (default 0 EUR). Missing, NaN, bool, string, negative, `unknown_cost: true` or `cost_class: "unknown"` raise `CostBlocked` before any journal write |
| RUN / VERIFY | the worker uses the controller API (`claim`, `start`, `heartbeat`, `result`) unchanged | Controller fencing, lease expiry and verifier rules apply |
| FINAL | `engine.finish_turn(slot, workkey, token, task_id, checkpoint)` | DONE only if the task is COMPLETE, `resolution == "verified"` and the journal holds its `RESULT_ACCEPTED`; the proof `journal:<seq>:RESULT_ACCEPTED` goes into checkpoint and receipt. FAILED/CANCELLED → `FAILED_FINAL`, BLOCKED → `BLOCKED`, anything else → `NOT_PROVEN` (workkey stays claimed). Stale token → `REJECTED_STALE_WRITER` |
| NEXT | `finish_turn` wakes the slot; `engine.next(slot)` returns the next workkey | Order: priority, then key |

Restart: the task id is derived from the workkey (`idempotency_key = "workkey:<key>"`), so `submit` after a restart returns the same task and nothing runs twice.

Limits (deliberate):
- The cost gate covers tasks created through the engine. Code that calls `Controller.create_task` directly bypasses it.
- All Kirby access for a campaign must go through one engine (or hold the same lock file); direct `Kirby` writes are not serialised.
- A human `EFFECT_CONFIRMED` completes a task with `resolution = "effect_confirmed"`; the engine does not count that as proof.
