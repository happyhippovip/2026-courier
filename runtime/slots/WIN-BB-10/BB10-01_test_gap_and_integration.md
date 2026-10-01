# WIN-BB-10 BB10-01 — Consolidated test-gap + integration-check (current SHA 329abd80)

TREE=fix-cb1-new @ 329abd80. SHELL=DOWN → static only; every verdict caps at
TEST_EXISTS_NOT_EXECUTED. No suite executed anywhere this session (nor runnable:
no conftest.py, no documented env, see G0). Deduped vs WIN-BB-01 PKG-C (matrix),
MUSE-45 T-P/T-S/T-U (worker pins), PAYG WIN-08 PKG-2 (mechanics baseline).

## G0. Execution blockers (infra; precede all pins)

- G0-a (HIGH): test_server_integration_contract.py:12 top-level `from server
  import app` (+ failure_recovery_matrix via :6-7) requires COURIER_API_KEY +
  COURIER_VERIFIER_API_KEY at COLLECTION (app.py:12-17 SystemExit). No
  conftest.py repo-wide; pytest.ini carries no env help; README has no testing
  section. Bare `pytest` collection-ERRORS without exported keys. (Cite
  V-PKG2-1; still open, no peer filed a fix.)
- G0-b (MEDIUM): ROOT-on-sys.path order dependence — 9 suites need ROOT, 6
  insert it, no __init__.py anywhere, no pythonpath config, egg-info is a
  STALE old-tree build. `python -m pytest` masks it; bare `pytest` may
  ModuleNotFound. Same conftest fix covers G0-a+G0-b.
- G0-c (MEDIUM): no requirements/pyproject/pins (Flask/pytest/PyYAML/werkzeug/
  requests/node all tribal). RUN1 needs an env spec.
- G0-d (MEDIUM): docstring drift — p3_preview ("patch series applied"), both
  P3 suite headers ("through the P3 cutover patch series"), docs/p3/README:16-17
  ("git apply --check is part of that test", "# P3 patch" section EMPTY, no such
  test) all describe a patch flow that does not exist; loader exercises LIVE
  code. .patch files are dead artifacts (retire or re-verify vs live code).

## G1. Pin gaps (ordered by value; writer/test-owner scope)

1. G1-omission (MEDIUM, NEW — D-BB-1): NO test posts a result whose refs OMIT
   an expected task artifact. Code accepts it (server iterates result-refs
   only app:377-379; verifier loops result arts only verifier:70-95). Needs
   FIX first (coverage rule) then pin. Distinct from peer BB01-NEW-1
   (local-lane expected VALUE), which is about value, not set coverage.
2. G1-local-expected (MEDIUM, peer-owned BB01-NEW-1 test): linux/github
   local-verify ignores task expected_sha256 (verifier:93). TEST_TO_ADD as
   specified in peer PKG-C. Listed here for tally, not re-derived.
3. G1-malformed-target (LOW): verifier :65-68 FAILs targets outside
   {linux,windows,mac,github}; zero pins. TEST_TO_ADD:
   verify_artifacts({"target_capability":"weird"},…) → FAIL. (Peer PKG-C agrees.)
4. G1-changed-status (LOW): 9-field equality incl. status (app:367) → 409
   (:369-370); no SUCCESS→FAILED-same-ids resend pin (adjacent conflict pins
   exist test_p3:92-118). Cheap ADD.
5. G1-changed-worker-409 (LOW): wrong-worker 400-leg pinned
   (failure_matrix:31-36); changed-worker resend on PROCESSED task → 409 leg
   unpinned. Cheap ADD. (Peer PKG-C agrees.)
6. G1-case4-dedicated (LOW, peer reading adopted): worker-supplied
   expected_sha256 KEY → 400 via strict key-set (contract:155-156); only
   adjacent shape pin exists (artifact_store:115). TEST_TO_ADD per peer PKG-C.
7. G1-A-to-B (LOW-MED, joint with peer G-BB2): index-advance pinned
   (server_contract:169); zero multi-step goals in ANY suite → B-dispatch
   after A-reconcile UNPINNED. TEST_TO_ADD: 2-step goal, reconcile A via
   verifier flow, claim → B packet (attempt:1, fresh dispatch).
8. G1-quarantine-resume-E2E (LOW-MED, NEW): reclaim→HUMAN_REQUIRED pinned
   (server_contract:368-415 incl. other-goal-continues + late-409); resume
   pinned only after FAILED_VERIFICATION (test_p3:52-64). No
   quarantine→resume(retry)→reclaim→REDISPATCH→RESULT chain pin. ADD (also
   re-validates F5-downgrade + release idempotence end to end).
9. G1-windows-live (MEDIUM, infra): all Windows-only surfaces mocked out of
   binding/contract suites (msvcrt, Popen/timeout, WMI, network) → real
   timeout-kill (G-C2), msvcrt no-stacking, N1/Q4 finally-PermissionError,
   Q9 handshake, stop.bat behavior UNPINNABLE without a Windows-marked live
   suite + Windows CI runner. Reuse tests/acceptance/ (currently excluded).
10. G1-claim-match (LOW): M5 substring/vocab/cost-deferral rules (app:286-325)
    exercised only via valid pairs; no targeted pin for mismatch declinations,
    unknown-cost neutrality, or "antigravity"→400 dead branch (D-BB-2). ADD
    after D-BB-2 decision.
11. G1-planner-real (LOW-MED): planner path pinned ONLY with mocked Chief
    (server_contract:214-237, incl. antigravity→mac normalization pin :236);
    REAL ChiefCommander (steward snapshot cost, D-BB-5 lock-hold) unpinned.
    ADD heartbeat-during-planner-goal concurrency test after D-BB-5 fix.
12. G1-stdout (INFO, needs D-BB-3 decision first): validate projection drops
    stdout/stderr (contract:172); pin either persistence (if kept) or
    absence-by-design.

## G2. Integration mechanics (verified current-SHA)

- I1: failure_matrix:74-81 "restart" = fresh CLIENT over same state file
  (comment says so). Peer case-8 PPR (no kill-and-resend test) DOWNGRADED to
  INFO: server is stateless-per-request (load per request; disk-backed
  artifact store; zero module-level caches — only keys/lock/store-root), so
  process restart is behaviorally identical to fresh client. Kill-test still
  nice-to-have, no longer a blocker.
- I2: concurrent-claim exactly-one-winner PINNED under adversarial save
  rendezvous (server_contract:311-365, ThreadPoolExecutor + coordinated save).
  Single-process RLock atomicity holds; residual is multi-PROCESS ONLY
  (-w 1 deployment pin, cite V-PKG4-4).
- I3: reregister-without-current_task preserves claim (server_contract:296-308)
  + unregister→register(None) quarantines (failure_matrix:90-98) → register
  release/retain branches both pinned (F6 family closed by tests).
- I4: corrupt state → JSONDecodeError raised, never silent-empty
  (server_contract:240-246). Fail-loud, consistent with daemon O2 crash.
- I5: revoke/auth matrix thorough (failure_matrix:47-71, server_contract:74-110:
  401/403, worker-key-cannot-verify, insecure-default-503, verifier-key-split).
- I6: mac E2E skips on win32 (upload_flow:331-332) — Windows-only CI never
  exercises mac upload lane; cross-platform CI or accept the blind spot.
- I7: unittest/pytest mix (thought/bodyguards/resource suites use unittest —
  collected fine); .mjs not pytest-collected; acceptance/boundaries excluded
  by design (helpers + server soak).
- I8 (weak pin, INFO): failure_matrix:25 posts conflicting result WITHOUT
  asserting status (stored-preservation asserted :26-28; 409 covered by
  test_p3:96). Suggest adding `== 409` assert when touching the file.

## Counts (static)

Five-file surface: upload_flow 15 tests + p3 9. Integration ring:
failure_matrix 9 fns (~30 w/ params), server_contract 16, contract 5,
identity_binding 2, artifact_store 11. All TEST_EXISTS_NOT_EXECUTED.
 temp/ residue (8 records + rejected w1) = unprovenanced run evidence, NOT
counted (cite V-PKG8-4).

## Disposition

READ ONLY. Gaps G1-1..12 to test-owner/Central Writer in the stated order
(G0 first — nothing runs until it does). No overlap with live peer filings:
peer owns matrix verdicts + BB01-NEW-1 + G-BB2 statement; this package owns
mechanics (I1 downgrade, I2 pin cite), the ordered gap list, and NEW items
G1-omission(D-BB-1)/G1-quarantine-resume/G1-planner-real/G1-claim-match.
