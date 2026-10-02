# User Acceptance Requirement 01: Grandma State Mapping (Dual-Surface Truth)

## 1. User-Visible Ambiguity
When a user queries `/goals/<goal_id>` or views the Courier status drawer, they receive raw engine state:
`"status": "ACTIVE"`, `"current_step_index": 1`, `"workflow_plan": [...]`.
The user cannot directly answer the three fundamental questions:
- Arbeitet Courier gerade?
- Braucht Courier mich?
- Ist Courier fertig?
Specifically:
- `"ACTIVE"` can mean Courier is actively computing on a worker, OR waiting for an unregistered worker, OR idle between tasks.
- `"BLOCKED"` does not specify whether human intervention is required, or if an automated recovery/quarantine is in progress.

## 2. What the System Can Actually Prove Today
The server runtime state (`state = load_state()`) deterministically records:
1. `goal["status"]` in `{"ACTIVE", "DONE", "BLOCKED"}`.
2. `current_step = goal["workflow_plan"][goal["current_step_index"]]`.
3. `step["status"]` in `{"QUEUED", "DISPATCHED", "RESULT_RECEIVED", "RECONCILED", "FAILED_VERIFICATION", "FAILED_TERMINAL", "HUMAN_REQUIRED"}`.
4. Assigned worker liveness: `now - worker["last_seen"] <= 300` and `worker["current_task"] == step["task_id"]`.

## 3. Concrete Acceptance Requirement
Every user-facing Goal presentation must map internal ledger fields deterministically into a 4-state user summary:
1. **`FERTIG`**: If `goal["status"] == "DONE"` (all workflow steps reconciled).
   - `action_required`: `false`
   - `user_message`: "Alle Aufgaben wurden erfolgreich abgeschlossen und verifiziert."
2. **`BRAUCHT_DICH`**: If `step["status"] in ("HUMAN_REQUIRED", "FAILED_TERMINAL")` or `goal["status"] == "BLOCKED"`.
   - `action_required`: `true`
   - `action_type`: `"RESUME_OR_RETRY"`
   - `user_message`: Plain explanation of the blocker without internal stack traces.
3. **`ARBEITET`**: If `step["status"] in ("DISPATCHED", "RESULT_RECEIVED")` and worker heartbeat is fresh.
   - `action_required`: `false`
   - `user_message`: "Courier arbeitet selbstständig an Schritt X von Y."
4. **`WARTET_AUF_KAPAZITAET`**: If `step["status"] == "QUEUED"` and no matching worker is currently active.
   - `action_required`: `false`
   - `user_message`: "Courier wartet auf einen verfügbaren Worker für Plattform X."

## 4. Required Runtime State & Evidence
- **State Fields**:
  - `state["goals"][goal_id]["current_step_index"]`
  - `state["goals"][goal_id]["workflow_plan"][i]["status"]`
  - `state["workers"][worker_id]["last_seen"]`
- **Evidence Verification**:
  - Pure deterministic helper `derive_user_state(goal, state)` returning `{user_state, user_message, action_required}`.
  - Regression test proving all 4 states map without contradictory or "UNKNOWN" outputs.
