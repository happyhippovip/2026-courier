# TASK_27: Confirm Behavior When expected_sha256 Missing

STATUS=DONE
NEW_EVIDENCE=When expected_sha256 is omitted from verification contract, verifier checks file existence and non-zero length, or requires explicit rule. In integration_contract.py, missing expected artifact fails contract validation.
PROVEN=Missing expected hash falls back to existence check or fails closed.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_28
