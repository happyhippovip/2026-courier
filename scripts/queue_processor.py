import os, glob, json, shutil, sys

try:
    from scripts.intake_dispatcher import (
        dispatch_intake, fingerprint_task_id, load_central_state,
        ADMISSION_ADMITTED, ADMISSION_DISPATCHING, ADMISSION_BLOCKED,
    )
except ImportError:
    from intake_dispatcher import (
        dispatch_intake, fingerprint_task_id, load_central_state,
        ADMISSION_ADMITTED, ADMISSION_DISPATCHING, ADMISSION_BLOCKED,
    )

def is_task_blocked(intake_file, state_file='central_state.json'):
    """True when this intake's fingerprint task is currently in ADMISSION_BLOCKED state."""
    try:
        with open(intake_file, 'r') as f:
            intake = json.load(f)
        state = load_central_state(state_file)
        task = state["tasks"].get(fingerprint_task_id(intake))
        if task is None:
            return False, None
        if task.get("admission") == ADMISSION_BLOCKED or task.get("state") == "BLOCKED":
            return True, task
        return False, task
    except (OSError, ValueError, KeyError):
        return False, None

def already_recorded(intake_file, state_file='central_state.json'):
    """True when this intake's fingerprint task is already ADMITTED.

    Crash between dispatch and the queue move leaves the intake pending
    but recorded; recovery must skip the second external dispatch. A
    DISPATCHING, BLOCKED, or UNBLOCKED marker is NOT recorded as admitted:
    it must fall through to dispatch_intake.
    Raises OSError/ValueError/KeyError when the answer is unknowable;
    callers fall through to dispatch (which fails closed itself).
    """
    with open(intake_file, 'r') as f:
        intake = json.load(f)
    state = load_central_state(state_file)
    task = state["tasks"].get(fingerprint_task_id(intake))
    if task is None:
        return False
    if task.get("admission") in (ADMISSION_DISPATCHING, ADMISSION_BLOCKED, "UNBLOCKED", "READY"):
        return False
    return True

def process_queue(admission_checker=None):
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)

    pending_files = glob.glob("intakes/pending/*.json")
    if not pending_files:
        return

    for intake_file in pending_files:
        print(f"Processing {intake_file}")
        try:
            # Check if task is already in BLOCKED state: prevent tight retry loop
            blocked, task_data = is_task_blocked(intake_file)
            if blocked:
                print(f"Task in {intake_file} is BLOCKED ({task_data.get('blocked_reason')}); skipping re-dispatch without model calls")
                continue

            try:
                recorded = already_recorded(intake_file)
            except (OSError, ValueError, KeyError):
                recorded = False
            if recorded:
                print(f"Already dispatched {intake_file}; skipping re-dispatch")
            else:
                if admission_checker is not None:
                    dispatch_intake(intake_file, admission_checker=admission_checker)
                else:
                    dispatch_intake(intake_file)

            # Check if dispatch marked task as BLOCKED on admission
            blocked, task_data = is_task_blocked(intake_file)
            if blocked:
                print(f"Task in {intake_file} blocked on admission ({task_data.get('blocked_reason')}); parked in pending")
                continue

            shutil.move(intake_file, os.path.join("intakes/processed", os.path.basename(intake_file)))
            print(f"Successfully processed and moved {intake_file}")
        except (Exception, SystemExit) as e:
            # dispatch_intake signals dispatch failure via sys.exit();
            # a poisoned intake must not abort the rest of the batch.
            print(f"Error processing {intake_file}: {e}")

if __name__ == "__main__":
    process_queue()
