# Follow-up: task view for bridge specs the goal-contract gate parks

The ledger bridge parks a mission, and does not post it, when `validate_task` does not accept the spec. Two existing bridge specs have no task view, so that gate parks them. This note only lists the fields a later change would add. It does not change those specs, their tests, or their lanes.

## Specs that park

Verified A-to-B input handoff (`tests/test_ledger_bridge_verified_inputs.py`, and the A-B-C-D chain that reuses its `_spec`). Each spec is `adapter`, `params`, `effect_class`, `max_attempts`, `lease_ttl_s`, and sometimes `inputs_from`. There is no goal contract.

Ledger chain specs that bind an upstream artifact (`bind_input` on a synthetic spec with `adapter`, `params`, `effect_class`, `max_attempts`, `lease_ttl_s`). There is no goal contract.

`inputs_from` and `bind_input` stay as they are. They are not a task view.

## Fields those specs need

Each spec needs these top-level fields. The bridge copies them onto the controller task. `validate_task` reads them there.

| Field | What it must be |
| --- | --- |
| `goal_id` | The id of one contract already stored in `<home>/goal_contracts.jsonl`. |
| `goal_fingerprint` | `GoalContract.fingerprint()` of that stored contract. A different fingerprint is `stale_fingerprint`. The mission stays parked. |
| `scope` | A list of strings. Each one is inside that contract's allowed scope and outside its forbidden scope. A wider list is `scope_widened`. |
| `acceptance_ids` | Ids of acceptance criteria that exist on that contract. |
| `evidence_class` | The evidence class those criteria require. For the synthetic artifact proof that is `deterministic`. |

The stored contract must already carry an authenticated human confirmation: `actor_kind` is `human`, and `actor_ref` is a named person, not anonymous and not an agent. The bridge does not confirm a contract and does not invent one. An unconfirmed contract is not stored, and a spec that names one is parked.

Until both the stored confirmation and these five fields are present, the mission is parked and no controller task is posted. `server/app.py` is a separate gap: a `workflow_plan` posted directly to `POST /goals`, and `POST /tasks/claim` on that process, never reach this controller.
