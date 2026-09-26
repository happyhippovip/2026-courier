# TASK_23: Content Verify: Newline-Variance Fixture

STATUS=DONE
NEW_EVIDENCE=CRLF vs LF variance: 'COURIER-A2B-A\r\n' has SHA-256 d1b4... vs 'COURIER-A2B-A\n' has 5751... Binary hash comparison fails on newline mismatch.
PROVEN=Strict binary hash verification does not tolerate newline normalization drift. Artifacts must be written with explicit '\n'.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_24
