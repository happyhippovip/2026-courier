# TASK_47: Physical Run Prep: Abort Conditions

STATUS=DONE
NEW_EVIDENCE=Mandatory abort triggers: 1. Candidate SHA mismatch. 2. Port collision on 8081. 3. Task A reaches FAILED_VERIFICATION. 4. A execution count > 1. 5. Any human HTTP call during autonomous window. 6. State corruption (500 Internal Server Error).
PROVEN=Fail-closed safety abort boundaries codified.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_48
