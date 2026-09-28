# WINDOWS CENTRAL WRITER BATCH 8 - 2026-09-28

## Substep 1: Fix Manual Workflow Plan Target Agent Normalization
**Error Detected:** When a user submitted a manual workflow plan with `"target_agent": "codex"`, the server did not normalize the target string (unlike when it generates plans using AI). The `check_capabilities` logic requires exact substrings (e.g. `"windows"`). Since `"codex"` does not match any worker capability, the task would hang in `QUEUED` forever.
**Fix Applied:** Refactored the target agent normalization logic into a helper function `normalize_target_agent` in `server/app.py`, and applied it to BOTH manual and AI-generated workflow plans.
**Test Added:** Added `test_manual_plan_target_agent_normalization` to `tests/test_p3_server_idempotency.py` to ensure `"codex"` is correctly normalized to `"windows"` and can be claimed by a Windows worker.

## Substep 2: Fix OOM Vulnerability in Verifier Artifact Fetching
**Error Detected:** `fetch_artifact` in `scripts/courier_verifier.py` fetched the entire artifact into memory via `requests.get().content` BEFORE checking its length against `MAX_ARTIFACT_BYTES`. If a malicious or rogue worker uploaded a huge artifact, the verifier would attempt to allocate the memory and crash with an OOM.
**Fix Applied:** Modified `fetch_artifact` to check the `size` reported by `/artifacts/<id>/meta` first, and then stream the artifact using `stream=True` and `iter_content`, checking the cumulative length in chunks to prevent memory allocation exhaustion.
**Test Added:** Created `test_verifier_oom.py` with `test_fetch_artifact_oom_prevention` mocking a large download chunk stream and verifying that the size limit exception is correctly raised before OOM occurs.

## Substep 3: Reject Empty Manual Workflow Plans
**Error Detected:** The `submit_goal` endpoint allowed users to supply an empty `workflow_plan: []`. Since `len(goal["workflow_plan"])` is 0, the current step index (0) is never strictly less than the length, so the goal would permanently hang in the `ACTIVE` state without ever progressing or terminating. AI-generated empty plans were already rejected properly.
**Fix Applied:** Added a check in `server/app.py` to return `400 Bad Request` if a manual `workflow_plan` is explicitly provided but empty.
**Test Added:** Added `test_empty_workflow_plan_is_rejected` to `tests/test_p3_server_idempotency.py` to prove that empty plans yield a 400.
