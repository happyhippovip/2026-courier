# Ledger engine contract (for A→B→C integrators)

`courier_runtime/ledger_engine.py` joins the journal controller (one task) and Kirby (which workkey is next).
It changes neither: `courier_core/controller.py` and `courier_runtime/continuity.py` stay as they are.

| Step | Call | Guarantee |
|---|---|---|
| QUEUE | `engine.add_workkeys([...])`, `engine.open_slot(slot, provider)` | Written under the campaign file lock |
| CLAIM | `engine.next(slot)` → `(workkey, token)` or `None` | One owner per workkey across processes (ownership is per slot: two processes sharing a slot name resume the same workkey and are fenced by token at FINAL); a slot that still owns a workkey gets it back |
| COST GATE | `engine.submit(workkey, task_body, slot=None, token=None)` → `task_id` | `params.estimated_cost_eur` must be a finite number ≤ spend limit (default 0 EUR). Missing, NaN, bool, string, negative, `unknown_cost: true` or `cost_class: "unknown"` raise `CostBlocked` before any journal write. A task that already exists for the workkey (restart, replay) is returned unchanged when the body is the same, without the gate; a different body raises `TaskConflict` (the controller's 409) and parks nothing. A body with `depends_on` is refused (`ValueError`): the engine orders work by workkey With `slot`/`token` the workkey is also parked BLOCKED (`COST_BLOCKED: …`) so the slot moves on |
| RUN / VERIFY | the worker uses the controller API (`claim`, `start`, `heartbeat`, `result`) unchanged | Controller fencing, lease expiry and verifier rules apply |
| FINAL | `engine.finish_turn(slot, workkey, token, task_id, checkpoint)` | DONE only if the task is COMPLETE, `resolution == "verified"` and the journal holds its `RESULT_ACCEPTED`; the proof `journal:<seq>:RESULT_ACCEPTED` goes into checkpoint and receipt; after a crash between the receipt line and the campaign save, the repeated `finish_turn` completes the state change without a second receipt. FAILED/CANCELLED → `FAILED_FINAL`, BLOCKED → `BLOCKED`, anything else → `NOT_PROVEN` (workkey stays claimed). A `task_id` that is not this workkey's → `REJECTED_FOREIGN_TASK`. Stale token → `REJECTED_STALE_WRITER` |
| NEXT | `finish_turn` wakes the slot; `engine.next(slot)` returns the next workkey | Order: priority, then key |

Restart: the task id is derived from the workkey (`task_id_for(workkey)`, the controller's id for `idempotency_key = "workkey:<key>"`), so `submit` after a restart returns the same task and nothing runs twice.

Journal reads take the controller lock, so the engine never sees a half-written append. The campaign lock waits indefinitely on POSIX (`flock`) and on Windows (`LK_NBLCK` retried every 50 ms; plain `LK_LOCK` would give up after about 10 s).

Limits (deliberate):
- The cost gate covers tasks created through the engine. Code that calls `Controller.create_task` directly bypasses it.
- All Kirby access for a campaign must go through one engine (or hold the same lock file); direct `Kirby` writes are not serialised.
- A human `EFFECT_CONFIRMED` completes a task with `resolution = "effect_confirmed"`; the engine does not count that as proof.

## Writers outside the engine
| Path | What it does today | Risk | Owner |
|---|---|---|---|
| `courier_core.controller.Controller.create_task` called directly | creates a task with no cost check | unknown cost reaches a worker (F-C1) | L2 (controller admission; open, no PR fixes it — #826 edits `controller.py` for other reasons) |
| `courier_runtime/host_loop.py` → `provider_events.handle` | a `TURN_ENDED outcome=DONE` line calls `engine.finish_turn` when the caller passes the existing LedgerEngine, and returns `NOT_PROVEN` with the workkey still claimed when no engine is passed. `main` does not construct a LedgerEngine. Tick, drain, IDLE, and HEARTBEAT reload under the campaign lock before they save | F-K1 and F-K2 are closed on this path. `continuity.py` is unchanged. A direct `Kirby.on_turn_end(..., "DONE")` outside this path is still not journal proof | L3, fixed on this branch |
| `scripts/ledger_v1_bridge.py` (PR #827) | cost gate only when the spec names `agent_id`, `host_id` or `estimated_cost_eur` | a local mission spec without those keys is dispatched without a cost check | Cursor A→B→C |

`tests/test_ledger_engine.py` still pins the direct `Controller.create_task` gap as `xfail(strict=True)` (F-C1). The host-loop gaps are passing tests: a DONE line without an engine stays claimed, and a stale in-memory CLAIMED image does not overwrite a journal-proven DONE.

## Fencing across the engine boundary
A write about a workkey is valid only if all of these hold at the moment of the write, checked under the campaign lock after a fresh load:
1. the slot's session holds the workkey (`session.workkey == workkey`, `workkey.owner == session.session_id`);
2. the caller's token equals the workkey's current token (bumped on every claim);
3. for FINAL, the controller journal holds the task's `RESULT_ACCEPTED` (task id derived from the workkey).

The capability is the triple (slot, workkey, token), never a bare token. Any writer of the campaign file that does not take the lock file `<campaign>.lock` and reload inside it is outside this guarantee. The host loop does both: a DONE line calls `finish_turn`, and every other save in `run_once` and `provider_events.handle` reloads inside that lock.

## Hand-off between Cursor's A→B→C path and the engine
| From | To | Contract |
|---|---|---|
| Cursor dispatcher / bridge | engine | create work only via `engine.submit(workkey, body, slot, token)`; `body.params.estimated_cost_eur` explicit; idempotency key is set by the engine |
| worker (any host) | controller | unchanged controller API: `claim`, `start`, `heartbeat`, `result`; artifacts with sha256 |
| controller | engine | read-only: `journal.task(task_id)` and the `RESULT_ACCEPTED` event; the engine never writes the journal except `create_task` |
| provider signal (`TURN_ENDED outcome=DONE`) | engine | a claim, not a fact: map it to `engine.finish_turn(...)`; the engine decides DONE from the journal |
| engine | Cursor / Kolibri | `kirby.json` workkey `state`, `checkpoint` (contains `journal:<seq>:RESULT_ACCEPTED` for DONE), `blocked_reason`; `receipts.jsonl` one line per DONE |
