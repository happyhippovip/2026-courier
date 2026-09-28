# Codex Handoff — Durable Final Candidate 2026-09-28

OWNER=SINGLE_DURABILITY_OWNER_MUSE / 2026-09-28
GATE_REF=ops/ai/GATE_STATE_CURRENT.md (PRE_CODEX_STATE=DURABLE, updated once)

## Durable identity
- FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
- BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9 (origin/candidate-b-1, old tip)
- REMOTE_REF=refs/heads/candidate-b-1 @ github.com/happyhippovip/2026-courier.git
- PUSH=fast-forward 4c1e24cc..34b0a426, PUSH_EXIT=0,
  ls-remote confirms origin/candidate-b-1==34b0a426. No new variant:
  exact gate-reported bytes pushed, zero source edits in this lane.

## Lineage / scope (BASE..FINAL, verified via diff --name-only)
- LINEAGE_OK: direct descendant of BASE_SHA.
- 22 files: 18 ops-ai/docs + 4 source files:
  scripts/courier_verifier.py, scripts/integration_contract.py,
  server/app.py, tests/test_artifact_upload_flow.py.
- CAVEAT_1: tests/test_p3_server_idempotency.py is NOT in this SHA delta;
  p3 coverage exists only in later local commits (09166bd5..e11749b6,
  detached HEAD, NOT pushed). Watcher 5-file expectation vs this SHA
  needs checklist-owner adjudication — not re-validated here.
- CAVEAT_2: diff --check BASE..FINAL reports whitespace noise, all in
  ops/ai docs (trailing whitespace, blank line at EOF). Source files clean.

## Evidence reused (no test re-runs in durability lane)
- ops/ai/WINDOWS_CENTRAL_WRITER_FINAL_COMMIT_2026-09-28.md (Q027 packet,
  pytest-checked per author; integration SHA 09166bd5 noted as LATER work,
  not part of FINAL_SHA).
- ..._2/_3/_4_2026-09-28.md: "pytest tests/ 100% passing (336 items)"
  per author, on later trees — cited, not re-run, not claimed for FINAL_SHA.

## Open for checklist owner (CODEX_GATE_CHECKLIST_OWNER)
1. Watcher 5 criteria from FINAL_SHA_GATE_WATCHER_REPORT_2026-09-27.md
   (scope exactness vs CAVEAT_1, whitespace, 12-case matrix, 44/44).
2. G071/G072 WAITING_FOR_FINAL_SHA: SHA now durable; replay/blocker
   adjudication stays in G-lane.
3. Later local writer stack (09166bd5..e11749b6) unpushed by design;
   only promote via new gate decision, never silently.

DO_NOT_REPEAT_FINGERPRINT=sha256-codex-handoff-durable-34b0a426-01
