if __name__ == "__main__":
    import sys
    print("Disabled in favor of OS-owned Courier Motor.")
    sys.exit(1)
import os, glob, json, shutil, sys

# Ensure we can import from scripts dir
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from intake_dispatcher import dispatch_intake

def process_queue():
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)

    pending_files = glob.glob("intakes/pending/*.json")
    if not pending_files:
        return

    for intake_file in pending_files:
        print(f"Processing {intake_file}")
        try:
            dispatch_intake(intake_file)
            shutil.move(intake_file, os.path.join("intakes/processed", os.path.basename(intake_file)))
            print(f"Successfully processed and moved {intake_file}")
        except Exception as e:
            print(f"Error processing {intake_file}: {e}")

if __name__ == "__main__":
    import sys
    print("Disabled in favor of OS-owned Courier Motor.")
    sys.exit(1)
