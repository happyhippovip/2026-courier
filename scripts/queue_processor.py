import os, glob, json, logging, shutil, sys

logger = logging.getLogger(__name__)

# Ensure we can import from scripts dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from intake_dispatcher import dispatch_intake

def process_queue():
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processing", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)

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
            shutil.move(claimed, os.path.join("intakes/processed", os.path.basename(claimed)))
            logger.info("processed and moved %s", claimed)
            ok += 1
        except (Exception, SystemExit) as e:
            # dispatch_intake signals dispatch failure via sys.exit();
            # a poisoned intake must not abort the rest of the batch.
            # The file stays in processing/ for triage (re-queue would risk
            # a second external dispatch).
            logger.error("error processing %s: %s", claimed, e)
            failed += 1
    logger.info("queue batch done: %d ok, %d failed, %d skipped", ok, failed, skipped)

if __name__ == "__main__":
    process_queue()
