# TASK_24 — Stale-Hash Fixture

STATUS=DONE

## Stale Hash Scenario
Worker caches an old expected_sha256 from a previous artifact version.
New artifact has different content (different SHA-256).
Worker submits: {expected_sha256: <old>, sha256: <new>}

## Verifier Behavior (candidate-b-1)
Server stores the NEW bytes (since worker uploaded them).
Verifier fetches new bytes, computes sha256 = NEW hash.
Compares against expected_sha256 = OLD hash → MISMATCH → FAIL.

## Protection
NO pass is possible with stale expected_sha256 unless bytes happen to be identical.
Stale artifact_id would reference the old blob → binding check would detect task/dispatch mismatch.

VERDICT=FAIL (correct)

PROVEN=Source-audited.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_25
