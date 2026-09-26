# TASK_25 — Empty-File Fixture

STATUS=DONE
FILE_LINE_EVIDENCE=scripts/courier_verifier.py:62-63

## Empty File Behavior
if not artifacts: log("No artifact evidence.") → FAIL immediately

## Zero-Byte Upload
If worker uploads empty file (0 bytes):
  sha256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  If expected_sha256 set to above hash: technically PASS for content check.
  But verify_uploaded_artifact also checks size field — size=0 would need to match claimed_size.
  In practice: zero-byte artifact for a real task is a semantic failure (no real output).

## Empty Artifacts List
Empty list → immediate FAIL at line 62-63.
This prevents pass with no evidence.

VERDICT=FAIL (empty artifacts list) or technical-PASS (zero-byte if hash matches, but semantic failure)

PROVEN=Source-audited. Empty artifact list rejected at entry.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_26
