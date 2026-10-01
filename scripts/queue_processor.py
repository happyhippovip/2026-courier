import os, glob, json, shutil, sys

# Ensure we can import from scripts dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from intake_dispatcher import dispatch_intake, fingerprint_task_id, load_central_state

def already_recorded(intake_file):
    """True when this intake's fingerprint task is already in state.

    Crash between dispatch and the queue move leaves the intake pending
    but recorded; recovery must skip the second external dispatch.
    Raises OSError/ValueError/KeyError when the answer is unknowable;
    callers fall through to dispatch (which fails closed itself).
    """
    with open(intake_file, 'r') as f:
        intake = json.load(f)
    state = load_central_state('central_state.json')
    return fingerprint_task_id(intake) in state["tasks"]

def process_queue():
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)

    pending_files = glob.glob("intakes/pending/*.json")
    if not pending_files:
        return

    for intake_file in pending_files:
        print(f"Processing {intake_file}")
        try:
            try:
                recorded = already_recorded(intake_file)
            except (OSError, ValueError, KeyError):
                recorded = False
            if recorded:
                print(f"Already dispatched {intake_file}; skipping re-dispatch")
            else:
                dispatch_intake(intake_file)
            shutil.move(intake_file, os.path.join("intakes/processed", os.path.basename(intake_file)))
            print(f"Successfully processed and moved {intake_file}")
        except (Exception, SystemExit) as e:
            # dispatch_intake signals dispatch failure via sys.exit();
            # a poisoned intake must not abort the rest of the batch.
            print(f"Error processing {intake_file}: {e}")

if __name__ == "__main__":
    process_queue()
