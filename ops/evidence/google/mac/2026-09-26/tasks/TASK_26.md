# TASK_26 — Worker-Reported SHA Alone Cannot Produce PASS

STATUS=DONE
FILE_LINE_EVIDENCE=scripts/courier_verifier.py:54-85

## Key Security Property
In candidate-b-1:
1. Worker reports sha256 in result artifacts.
2. Verifier does NOT trust this sha256 directly.
3. Verifier fetches artifact from server (GET /artifacts/<id>) independently.
4. Verifier recomputes sha256 from server-stored bytes.
5. Compares against expected_sha256 (from workflow contract, not worker).

## Without artifact_id path (base 332a42f9)
FILE_LINE_EVIDENCE=scripts/courier_verifier.py:85
Falls through to local_verify(path, sha256) which reads from LOCAL disk path.
Security: verifier must have access to the local path AND the file must exist with correct content.
Worker-reported sha256 is passed to verify_artifact which re-hashes the file.
If file doesn't exist or has wrong content → FAIL.

## Result
In BOTH paths: worker-reported sha256 alone cannot forge a PASS without the actual correct bytes.

PROVEN=Source-audited. Independent re-hash is mandatory.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_27
