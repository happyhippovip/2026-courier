import json
import sys
import subprocess
import hashlib
from pathlib import Path

if __package__:
    from .agent_handoff_ledger import atomic_write, writer_lock
else:
    from agent_handoff_ledger import atomic_write, writer_lock


def _payload(intake):
    """Fingerprint the effective workflow inputs, including existing defaults."""
    fields = ("target_owner", "target_repo", "target_sha", "customer_reference")
    if not isinstance(intake, dict):
        raise ValueError("Intake must be an object")
    payload = {key: intake.get(key) for key in fields}
    payload["price_currency"] = intake.get("price_currency", "EUR_99")
    payload["delivery_destination"] = intake.get("delivery_destination", "none")
    if any(not isinstance(value, str) or not value.strip() for value in payload.values()):
        raise ValueError("Workflow inputs must be non-empty strings")
    return payload


def _load_state(path):
    if not path.exists():
        return {"tasks": {}}
    # A corrupt/unreadable state is not permission to dispatch or erase history.
    with path.open(encoding="utf-8") as stream:
        state = json.load(stream)
    if not isinstance(state, dict) or not isinstance(state.get("tasks"), dict):
        raise ValueError("Invalid intake state; reconciliation required")
    if any(not isinstance(task, dict) for task in state["tasks"].values()):
        raise ValueError("Invalid intake task; reconciliation required")
    return state

def dispatch_intake(intake_file):
    with open(intake_file, encoding="utf-8") as stream:
        payload = _payload(json.load(stream))
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    task_id = f"task-revenue-{fingerprint}"
    state_file = Path("central_state.json")
    cmd = ["gh", "workflow", "run", "revenue_v1_baseline.yml"]
    for key, value in payload.items():
        cmd.extend(["-f", f"{key}={value}"])

    # Reuse existing atomic persistence/OS locking; no second queue or journal.
    with writer_lock(state_file, timeout=5):
        state = _load_state(state_file)
        previous = state["tasks"].get(task_id)
        if previous:
            if previous.get("intake_fingerprint") != fingerprint:
                raise RuntimeError("Intake identity conflict; reconciliation required")
            if previous.get("dispatch_accepted") is True:
                print(f"Reusing accepted dispatch for {task_id}")
                return task_id
            raise RuntimeError(f"Dispatch outcome unknown for {task_id}; reconcile before retry")
        for task in state["tasks"].values():
            if (task.get("customer_reference") == payload["customer_reference"]
                    and task.get("worker_id") == "github-actions-revenue-v1"
                    and not task.get("intake_fingerprint")):
                raise RuntimeError("Legacy intake is unbound; reconcile before dispatch")

        task = {
            "task_id": task_id,
            "intake_fingerprint": fingerprint,
            "customer_reference": payload["customer_reference"],
            "worker_id": "github-actions-revenue-v1",
            "platform": "github",
            "dispatch_ref": "intake_dispatcher_local",
            "execution_ref": None,
            "dispatch_accepted": False,
            "state": "DISPATCH_OUTCOME_UNKNOWN",
            "last_transition": "DISPATCH_INTENT_DURABLE",
            "next_explicit_transition": "RECONCILE_EXTERNAL_DISPATCH",
            "real_wall": "EXTERNAL_DISPATCH_OUTCOME_UNKNOWN",
        }
        state["tasks"][task_id] = task
        # Persist before crossing the external boundary. A crash/timeout must
        # leave a discoverable attempt that cannot be automatically redispatched.
        atomic_write(state_file, state)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Dispatch outcome unknown for {task_id}; reconcile before retry") from exc

        task.update(
            dispatch_accepted=True,
            state="DISPATCHED_TO_EXTERNAL",
            last_transition="DISPATCH_ACCEPTED",
            next_explicit_transition="BIND_EXTERNAL_EXECUTION",
            real_wall="EXACT_EXECUTION_BINDING_REQUIRED",
        )
        atomic_write(state_file, state)
        # `gh workflow run` does not return a bound run ID. The most recent run
        # may belong to another request; never manufacture that association.
        print(f"Dispatch accepted for {task_id}; exact external execution binding remains pending.")
        return task_id

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    dispatch_intake(sys.argv[1])
