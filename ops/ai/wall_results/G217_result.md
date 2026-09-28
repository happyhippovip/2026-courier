# Result for G217: Server-byte hashing boundary

TASK_ID=G217
STATUS=PROVEN
HOST=MAC
PROVIDER=GOOGLE_CLI
INPUTS_READ=scripts/courier_verifier.py
RESULTS_REUSED=scripts/courier_verifier.py
OUTPUT_REF=Hash boundary verified: Verifier streams bytes directly from server HTTP endpoint into `hashlib.sha256()`. Worker client metadata is never used for verification.
MISSING=None
BLOCKER=None
NEXT_DEPENDENCY=NONE
DO_NOT_REPEAT_FINGERPRINT=G217_SERVER_BYTE_HASHING_BOUNDARY_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-d7052b8e039a2422
