import os, glob, json, logging, shutil, sys

logger = logging.getLogger(__name__)

# Ensure we can import from scripts dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from intake_dispatcher import dispatch_intake

MARKER_SUFFIX = ".dispatched"

def _mark_dispatched(claimed):
    """Durable marker AFTER a successful external dispatch, BEFORE the move.

    Crash order guarantees: marker only exists if dispatch happened, so a
    marker + sibling in processing/ is always safe to move without
    re-dispatching; a crash before the marker leaves no marker (triage
    path, never auto-retried, so no second external dispatch is possible).
    """
    with open(claimed + MARKER_SUFFIX, "w", encoding="utf-8") as f:
        f.write("dispatched\n")
        f.flush()
        os.fsync(f.fileno())

def _recover_processing():
    """Move marker-backed files to processed/; report the triage backlog."""
    recovered = 0
    for marker in glob.glob(os.path.join("intakes/processing", "*" + MARKER_SUFFIX)):
        sibling = marker[: -len(MARKER_SUFFIX)]
        try:
            if os.path.isfile(sibling):
                shutil.move(sibling, os.path.join("intakes/processed", os.path.basename(sibling)))
                recovered += 1
            os.remove(marker)
        except OSError as e:
            logger.error("error recovering %s: %s", marker, e)
    if recovered:
        logger.info("recovered %d dispatched-but-unmoved intake(s)", recovered)
    backlog = sorted(os.path.basename(p) for p in glob.glob("intakes/processing/*.json"))
    if backlog:
        logger.info("processing backlog awaiting triage (%d): %s", len(backlog), ", ".join(backlog))
    return recovered

def process_queue():
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processing", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)

    _recover_processing()

    pending_files = glob.glob("intakes/pending/*.json")
    if not pending_files:
        return

    ok, failed, skipped = 0, 0, 0
    for intake_file in pending_files:
        # Atomic claim (AUTO-107): only the rename winner dispatches.
        claimed = os.path.join("intakes/processing", os.path.basename(intake_file))
        try:
            os.rename(intake_file, claimed)
        except FileNotFoundError:
            logger.info("skipped already-claimed %s", intake_file)
            skipped += 1
            continue
        logger.info("processing %s", claimed)
        try:
            dispatch_intake(claimed)
            _mark_dispatched(claimed)
            shutil.move(claimed, os.path.join("intakes/processed", os.path.basename(claimed)))
            try:
                os.remove(claimed + MARKER_SUFFIX)
            except OSError as e:
                # Harmless: the recovery prologue removes orphan markers.
                logger.error("error removing marker for %s: %s", claimed, e)
            logger.info("processed and moved %s", claimed)
            ok += 1
        except (Exception, SystemExit) as e:
            # dispatch_intake signals dispatch failure via sys.exit().
            # Exit 2 means the gh CLI is missing: an environmental failure,
            # not per-file poison. Stop the batch and return this file to
            # pending/ so nothing is triaged as poison and nothing is lost;
            # the next run retries when the environment is fixed.
            if isinstance(e, SystemExit) and e.code == 2:
                logger.error("environmental failure (%s); returning %s to pending and stopping batch", e, claimed)
                try:
                    os.rename(claimed, os.path.join("intakes/pending", os.path.basename(claimed)))
                except OSError as re:
                    logger.error("error returning %s to pending: %s", claimed, re)
                    failed += 1
                break
            # A poisoned intake must not abort the rest of the batch.
            # The file stays in processing/ for triage (re-queue would risk
            # a second external dispatch).
            logger.error("error processing %s: %s", claimed, e)
            failed += 1
    logger.info("queue batch done: %d ok, %d failed, %d skipped", ok, failed, skipped)

if __name__ == "__main__":
    process_queue()
