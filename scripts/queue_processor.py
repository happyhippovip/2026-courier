import os, glob, json, shutil, sys, time

# Ensure we can import from scripts dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from intake_dispatcher import (
    dispatch_intake, fingerprint_task_id, load_central_state,
    ADMISSION_ADMITTED, ADMISSION_DISPATCHING,
)

def already_recorded(intake_file):
    """True when this intake's fingerprint task is already ADMITTED.

    Crash between dispatch and the queue move leaves the intake pending
    but recorded; recovery must skip the second external dispatch. A
    DISPATCHING marker is NOT recorded: it must fall through to
    dispatch_intake so recovery adopts the in-flight run (or stays
    pending / re-dispatches once stale) instead of skipping it.
    Raises OSError/ValueError/KeyError when the answer is unknowable;
    callers fall through to dispatch (which fails closed itself).
    """
    with open(intake_file, 'r') as f:
        intake = json.load(f)
    state = load_central_state('central_state.json')
    task = state["tasks"].get(fingerprint_task_id(intake))
    if task is None:
        return False
    if task.get("admission", ADMISSION_ADMITTED) == ADMISSION_DISPATCHING:
        return False
    return True

# A deterministically-poison intake (e.g. invalid JSON) can never dispatch:
# identical state repeats beyond limit. Park it after this many consecutive
# failures so the batch advances past it instead of retrying it forever.
POISON_QUARANTINE_AFTER = 5


def _counts_path():
    return os.path.join("intakes", ".failure_counts.json")


def _symlink_queue_dir():
    """A symlink at the queue root or one of the directories inside it."""
    for path in ("intakes", "intakes/pending", "intakes/processed", "intakes/quarantine"):
        if os.path.islink(path):
            return path
    return None


def _load_counts():
    path = _counts_path()
    # A symlink is not a local count. True would be one prior failure; a
    # foreign 4 would park the intake on the next error. Leave the link in
    # place and count from zero. The following save replaces the directory
    # entry and does not write the link target.
    if os.path.islink(path) or os.path.islink(os.path.dirname(path)):
        return {}
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_counts(counts):
    try:
        os.makedirs("intakes", exist_ok=True)
        tmp = _counts_path() + ".tmp"
        with open(tmp, 'w') as f:
            json.dump(counts, f)
        os.replace(tmp, _counts_path())
    except OSError:
        # Best-effort only: counts accelerate quarantine but must never
        # break dispatch (e.g. under test doubles that stub makedirs).
        pass


def _record_success(intake_file):
    counts = _load_counts()
    if counts.pop(os.path.basename(intake_file), None) is not None:
        _save_counts(counts)


def _record_failure(intake_file, error):
    """Count one failed attempt; quarantine at the bound. Returns attempts."""
    counts = _load_counts()
    key = os.path.basename(intake_file)
    raw = counts.get(key, 0)
    # Bool is an int. True would become one prior failure and the poison
    # intake would keep being retried. An undecidable count is parked now.
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        attempts = POISON_QUARANTINE_AFTER
    else:
        attempts = raw + 1
    if attempts >= POISON_QUARANTINE_AFTER:
        linked = _symlink_queue_dir()
        if linked:
            print(f"Refusing to follow a symlink: {linked}", file=sys.stderr)
            return attempts
        try:
            os.makedirs("intakes/quarantine", exist_ok=True)
            dest = os.path.join("intakes/quarantine", key)
            if os.path.islink(dest):
                print(f"Refusing to follow a symlink: {dest}", file=sys.stderr)
                return attempts
            shutil.move(intake_file, dest)
            with open(dest + ".reason.json", 'w') as f:
                json.dump({"file": key, "failures": attempts,
                           "last_error": str(error),
                           "quarantined_at": time.time()}, f)
        except OSError:
            # File vanished mid-quarantine (moved externally): nothing to park.
            pass
        counts.pop(key, None)
    else:
        counts[key] = attempts
    _save_counts(counts)
    return attempts


def process_queue():
    linked = _symlink_queue_dir()
    if linked:
        print(f"Refusing to follow a symlink: {linked}", file=sys.stderr)
        return
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
            _record_success(intake_file)
        except (Exception, SystemExit) as e:
            # dispatch_intake signals dispatch failure via sys.exit();
            # a poisoned intake must not abort the rest of the batch.
            print(f"Error processing {intake_file}: {e}")
            _record_failure(intake_file, e)

if __name__ == "__main__":
    process_queue()
