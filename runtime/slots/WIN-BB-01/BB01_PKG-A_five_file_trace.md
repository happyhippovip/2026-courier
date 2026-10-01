# WIN-BB-01 PKG-A — Final-five file candidate trace

TREE=fix-cb1-new @ 329abd80 (HEAD, loose ref) | CANONICAL_BASE=candidate-b-1 @ 4c1e24cc (packed, local==origin)
FINAL_SHA=ABSENT (no `final*` ref under .git/refs; no FINAL_SHA hit in docs/ops/reports/handoffs) → no final verification possible; trace is CURRENT-TREE.
SHELL=DOWN → all verdicts static (PROVEN_BY_CODE / TEST_EXISTS_NOT_EXECUTED max). No test executed anywhere this session.

## The five files (all present, all fully read)

1. server/app.py — 562 lines. 16 routes: /health /status /goals(POST) /goals/<id> /workers /walls
   /workers/register /workers/unregister /workers/heartbeat /tasks/claim /tasks/result
   /tasks/reclaim_stale /tasks/pending_verification /tasks/verify /tasks/<id>/resume + artifact
   blueprint (POST /artifacts, GET /artifacts/<id>[/meta]). Import-gated on COURIER_API_KEY +
   COURIER_VERIFIER_API_KEY (SystemExit :12-17). All mutations under STATE_LOCK RLock (:47-53).
   REMOVED vs old rev (confirm HARVESTER): provider_wait/WAITING_PROVIDER, approve_merge,
   attestations, batches lane, health2. Zero `provider` hits claimed by WIN-01 MASTER_6C; consistent.
2. scripts/integration_contract.py — 172 lines. TASK_STATES (7, no READY/RUNNING/QUEUED-ultz),
   RESULT_STATES {SUCCESS,FAILED}, WORKER_IDS map. prepare_task (:43-63) defaults attempt/dispatch/
   worker/run/result/artifacts/status. verify_result (:66-112) LOCAL observation → deterministic
   result_id; ZERO prod callers (only tests). validate_durable_result (:115-172) REMOTE validation,
   exact artifact key-sets (:155-156); sole prod caller server/app.py:376.
3. scripts/courier_verifier.py — 153 lines. verify_artifact (local hash), fetch_artifact (server copy),
   verify_artifacts (:54-95): no-evidence→FAIL, malformed-target→FAIL (:65-68), uploaded→re-hash+
   expected_sha256-check (:71-89), remote-non-uploaded→FAIL (:90-92), local→safe-name+local_verify (:93).
   run_loop polls /tasks/pending_verification every 5s, posts /tasks/verify; revenue lane shells to
   revenue_v1_safety_baseline.py with argv list (no shell).
4. tests/test_artifact_upload_flow.py — 381 lines, 17 tests (parametrized count higher): upload
   accept/reject matrix, binding/name/claim checks, size limit, foreign-artifact rejection, verifier-key
   gating, verifier re-hash + tamper detection, expected_sha256 3-way, remote-path refusal, no-evidence,
   fetch-fail, Windows daemon E2E (upload+reconcile, transient-fault no-reexec, changed-after-hash
   release, upload-off-by-default), Mac E2E (skips on win32).
5. tests/test_p3_server_idempotency.py — 135 lines, 9 tests: step-mirror, FAIL→resume→fresh-attempt
   (old result 400), force_success refused, resume-route-before-main guard, ACK_DUPLICATE resend,
   conflict→409 + stored-preserved, FAILED-resend-ACK after requeue, changed-artifacts→409, unregister
   stickiness + re-register recovery.

## Load-bearing support files (read, not in the five)

- tests/p3_preview.py (31 lines): load_patched_server does NOT apply patches — loads live
  server/app.py; PATCH/PATCHES constants unused; docstring ("patch series applied") is FALSE.
  Consequence: both P3 test files exercise LIVE code; docs/p3/*.patch are dead artifacts.
  (Corroborates PAYG WIN-08 V-PKG3-2; filed once, not re-argued.)
- scripts/artifact_store.py (218 lines, fully read): put() server-hash + claimed-match + atomic
  blob/record writes; check_reference() binding/name/sha/size gate (NO expected_sha256 check);
  verify_uploaded_artifact() verifier-side re-hash + full binding check; blueprint enforces
  DISPATCHED-only upload + name-in-expected + worker/verifier key split.
- scripts/windows_worker/daemon.py (378 lines, fully read): claim→CLAIMED→STARTED→RESULT_READY→
  upload→post state machine; 4xx→REJECTED→release, 5xx/transport→UNDELIVERED→keep; crash-STARTED→
  release (never replay); msvcrt lock; NO kill on communicate timeout (:214-224) — orphan stands
  (cite V-PKG1-1 / MASTER_6C row 4 / MW1-D1, not re-filed).

## Dedupe (read, not duplicated)

WIN-01 MASTER_6C (8-row retry matrix, G-C1/C2/C3), WIN-01 MW1 (D1-D6; NOTE MW1-D4 Windows-tasklist
lock description is STALE — current daemon is msvcrt :252-264), WIN-06 POOL_WIN-004 (R1-R6; MIXED-rev:
daemon marker-bytes/AMBIGUOUS_CRASH refs are old-tree), MUSE-45 T8/T12/T14, ZERO-POOL Z04/Z06/Z07
(checklists stand, not re-derived), PAYG PKG-1..5 (current-SHA, adopted as baseline).
