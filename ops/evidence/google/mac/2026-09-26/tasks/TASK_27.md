# TASK_27 — Behavior When expected_sha256 Missing

STATUS=DONE
FILE_LINE_EVIDENCE=scripts/courier_verifier.py:74

## When expected_sha256 Not Present in artifact ref
if "expected_sha256" in art:   ← only checked if key present
    ...

## Behavior Without expected_sha256
1. If artifact_id path: verify_uploaded_artifact() runs → checks binding only (goal/task/attempt/dispatch/worker match), NOT content hash against contract.
2. If local path: local_verify(path, sha256) → re-hashes file, compares against worker-reported sha256 only.

## Security Implication
Without expected_sha256, verification is binding-anchored (correct task/dispatch) but not content-anchored (any content passes if sha256 internally consistent).
For Canary 1: expected_sha256 MUST be set in workflow plan contract to prove deterministic content.

## Canary Contract Requirement
workflow plan step must include expected_sha256 = 96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c for canary_A.txt

PROVEN=Source-audited. expected_sha256 is optional in code but REQUIRED for content proof in Canary.
UNKNOWN=Whether workflow plan contract in canary state includes expected_sha256.
BLOCKER=None (Canary 1 run_canary.sh bakes expected_sha256 into verify payload directly)
NEXT=TASK_28
