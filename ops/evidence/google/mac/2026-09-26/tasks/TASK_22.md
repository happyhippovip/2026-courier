# TASK_22 — Wrong-Content Fixture

STATUS=DONE (source-audited)

## Wrong Content Test
Scenario: worker submits artifact with correct path but wrong content.

FILE_LINE_EVIDENCE=scripts/courier_verifier.py:74-76
BEHAVIOR=Verifier fetches server-stored bytes, computes SHA-256, compares against expected_sha256:
  computed_sha256 ≠ expected_sha256 → log "Hash mismatch" → return FAIL

## If artifact_id path (candidate-b-1)
Worker uploads wrong bytes → server hashes them and stores → artifact_id bound to wrong-content blob.
Verifier fetches wrong-content blob → SHA-256 ≠ expected_sha256 → FAIL.
Worker-reported sha256 in result is ignored for verification decision.

VERDICT=FAIL (correct behavior — wrong content rejected)

PROVEN=Source-audited. Wrong content cannot produce PASS.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_23
