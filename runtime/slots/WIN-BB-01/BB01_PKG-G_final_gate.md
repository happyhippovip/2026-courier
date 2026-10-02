# WIN-BB-01 PKG-G — Final-gate readiness (current SHA 329abd80)

## FINAL_SHA gate: NOT TRIGGERED (absent)

- No `final*` ref under .git/refs (HEAD=fix-cb1-new @329abd80 loose; packed-refs has no FINAL_*).
- No FINAL_SHA/FINAL_FIVE/FINAL_MINIMAL_DELTA hits in docs/ops/reports/handoffs/scripts/server/tests.
- WORKROOT heartbeat (responsibility_wall/WIN-BB-01/heartbeat.txt): "I am waiting for CENTRAL WRITER
  to update the SHA." → no mint yet. Per mission: did NOT wait; produced PKG-E/F/G instead.
- runtime/proof/ ABSENT (read → os error 2): zero physical-proof evidence in-tree.

## Readiness verdicts

- CODEX_READY=NO — no FINAL_SHA to review; candidate-b-1 bytes (@4c1e24cc) unverifiable from this
  host (shell down, objects unreadable); worktree @329abd80 traced instead. Handoff claims
  SAFE_FOR_CODEX_REVIEW=YES but TEST_RESULTS=SKIPPED_EXISTING_EVIDENCE_IN_REPORTS (SKIPPED≠PASS).
- RUN1_READY=NO — 0 tests executed anywhere (shell down); 12-case matrix maxes at
  TEST_EXISTS_NOT_EXECUTED; reload leg PPR; 4 dedicated-pin gaps open (4,7,10-resend,+9-optional);
  BB01-NEW-1 (case-5 local) + BB01-5 (github lane stall) + BB01-2 (antigravity 400-loop) unaddressed.
- RUN2_READY=NO — same as RUN1 plus: no multi-step A→B pin (G-BB2), no executed canary, github lane
  structurally unable to reconcile (BB01-5).

## Scope question for the mint (Central Writer must resolve BEFORE minting)

- Mission FINAL_FIVE: courier_verifier.py, integration_contract.py, test_artifact_upload_flow.py,
  server/app.py, test_p3_server_idempotency.py.
- Handoff CHANGED_FILES (FINAL_CANDIDATE_HANDOFF.md): server/app.py, courier_verifier.py,
  windows_worker/daemon.py, test_p3_server_idempotency.py, test_artifact_upload_flow.py, p3_preview.py.
- DELTA: handoff swaps integration_contract.py OUT for daemon.py + p3_preview.py. Exactly-one-of the
  two lists must win at mint; "no sixth file" is only checkable after this resolves. Additional mint
  input (BB01-4): mint from LIVE worktree bytes, NOT from docs/p3/*.patch — the patches are dead
  artifacts AND the live ACK rule (9-field) is stricter than the patch (3-field); minting from
  patches would regress case 10.

## Environment deltas vs PKG-D (same slot, later session)

- PKG-D recorded WORKROOT=C:\Users\lol\courier_work\ as NOT_FOUND_ON_HOST. In THIS session the path
  EXISTS and is readable: full census done (google_queue_50 50+2 files, muse_45_longrun backlog 70+
  + claims + reports + results, reports/ handoff + google_win_queue_50 + GW2/MW3/MW5/NIGHT_HARVESTER,
  responsibility_wall/WIN-BB-01 heartbeat + WIN-BB-11, wall_10_20260926). PKG-D's NOT_FOUND verdict
  is STALE for this session; pool evidence was available and used for dedupe.
- candidate-b-2: REJECTED (carried, zero additional spend per mission).
- deploy/run-supervisor.sh re-read: gunicorn -w 1 --threads 4 + "avoid file locking" comment
  (V-PKG4-4 re-CONFIRMED on current SHA; -w 1 soft-pin residual stands).

## Stale marks (this session)

- STALE_SOURCE=docs/p3/*.patch WHY_STALE=fully landed in live code + idempotency rule superseded
  (3→9 fields) CURRENT_REPLACEMENT=live server/app.py bytes DO_NOT_REPEAT=patch-content audits.
- STALE_SOURCE=tests/p3_preview.py docstring + PATCH/PATCHES constants + both P3 test-file docstrings
  ("patch applied in temp copy") WHY_STALE=loader never applies anything; exercises live code.
- STALE_SOURCE=docs/p3/README.md "git apply --check is part of that test" WHY_STALE=no git/subprocess
  invocation in the loader or tests (imports only). Cited PAYG V-PKG3-2.
- STALE_SOURCE=PKG-D WORKROOT-NOT_FOUND (see above).

## Role-family coverage this session (stop-rule accounting)

Areas inspected (≥5 required): (1) backbone five files + patches, (2) mac worker lane, (3) github
lane (adapter+dispatcher+workflow), (4) watchdog/supervisor deploy wiring, (5) peer corpus
(WORKROOT + in-repo slots A-D), (6) full tests/ pin sweep, (7) git/packed-refs/proof state. Role
families touched (≥3 required): FINAL_FIVE_TRACE (primary, adopted+verified), BACKBONE_TRACE
(deltas), EVIDENCE_MATRIX (reverify), VERIFIER_FAIL_CLOSED (BB01-5/BB01-2 adjacent), TEST_GAP
(PKG-F). No new useful read-only work identified beyond this package — remaining items need shell
(execute tests, git ancestry/diff, process evidence) or the Writer (mint, BB01-2/5/NEW-1 fixes).

NEXT_EXACT_ACTION=whoever gets a shell first: (1) run the 9 test_p3_server_idempotency + 15
test_artifact_upload_flow + 8 test_failure_recovery_matrix tests with keys exported (pins the
TENE→EXECUTED jump for cases 1,2,3,5-remote,8-noreload,11,12); (2) `git diff candidate-b-1 HEAD`
scoped to the five/six files (resolves the mint-source question with bytes, not prose).
