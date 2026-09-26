# TASK_02: Final Windows Candidate Ref/SHA Availability

STATUS=DONE
NEW_EVIDENCE=Windows candidate ref origin/candidate-b-1 is confirmed present and fetched locally. Latest commit is 4c1e24ccc522042af826bc4c2b595daf85d097f9 (authored by Google Windows, 2026-09-26T17:19:41+0200: "fix: daemon powershell encoding and robust locking"). Preceded by 7b993162 ("chore: Candidate B verification implementation") and 8173f17e ("fix(server): resolve idempotency and artifact flow bugs"). Full tree includes artifact store, expected_sha256 verification in courier_verifier.py, and server duplicate protection in server/app.py.
PROVEN=CANDIDATE_AVAILABLE=YES. Candidate branch=origin/candidate-b-1, Candidate SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9.
UNKNOWN=None.
BLOCKER=None (Candidate B is published and physically inspectable).
NEXT=TASK_03

## UPDATE 17:55 — Candidate B-2 Binding & Verification
NEW_EVIDENCE=Windows candidate ref origin/candidate-b-2 published at commit 83940de3d7d33776a712e7506aa76726d16f8587 ("fix(server): acknowledge duplicate results properly when status omitted").
PROVEN=Candidate B-2 verified locally on Mac. 31/31 unit tests pass (test_p3_server_idempotency.py, test_artifact_upload_flow.py). Hermetic canary execution on port 8081 proves A->VERIFY->B and deterministic restart/no-replay.
CANDIDATE_BRANCH=candidate-b-2
CANDIDATE_SHA=83940de3d7d33776a712e7506aa76726d16f8587
