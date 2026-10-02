# WIN-BB-01 PKG-B — Backbone link trace (GOAL → CONTINUE)

TREE=fix-cb1-new @ 329abd80. Format per link: CODE_PATH / STATE_FIELD / PERSISTENCE / IDENTITY / FAILURE / TEST / UNKNOWN.

1. GOAL — CODE=server/app.py:94-151 submit_goal (workflow_plan inline, else ChiefCommander planner
   fallback :120-147). STATE=goals{goal_id:{status,workflow_plan[],current_step_index}}. PERSIST=
   central_state.json atomic save (:65-72). ID=goal-<8hex>. FAIL=400 no-goal_text; 503 planner fail/
   empty. TEST=test_p3 (setup_claimed_task inline-plan), upload_flow setup. UNKNOWN=planner output
   quality (ChiefCommander unread — out of five-file scope).
2. CONTRACT — CODE=integration_contract.py prepare_task (:43-63) + validate_durable_result (:115-172);
   verify_result test-only (zero prod callers). STATE=TASK_STATES 7 (QUEUED DISPATCHED RESULT_RECEIVED
   RECONCILED FAILED_VERIFICATION FAILED_TERMINAL HUMAN_REQUIRED) — no READY/RUNNING. PERSIST=n/a
   (pure functions). ID=attempt `task:attempt:N`, dispatch `dispatch-<hex>`, worker map WORKER_IDS.
   FAIL=ContractError→400/409 at claim/result/upload. TEST=test_integration_contract,
   test_result_identity_binding, test_artifact_store:100-117. UNKNOWN=none.
3. TASK — CODE=workflow_plan steps + mirror state["tasks"] (claim :345). STATE=step{task_id,
   instruction,target_agent,status,attempts,artifacts[]}. PERSIST=central_state.json (dual-write
   task+step, mirrored on result :397-402 / verify :511-513 / resume :537-540). ID=task-<8hex> or
   given. FAIL=superseded attempt 400 (contract :139-141). TEST=resume-fresh-attempt pin
   (test_p3:52-64). UNKNOWN=none.
4. CLAIM/LEASE — CODE=app.py:260-350 claim_task. Worker must be known+available+task-free (:268-275
   WORKER_BUSY). Single-head index gating (:279-281). Substring target match + exact capability
   (:286-290; "mac"→"macos" asymmetry, cite V-PKG4-1). Silent cost deferral (:296-325, cite V-PKG4-2).
   Mints attempt+1/dispatch uuid via prepare_task (:328-336), DISPATCHED, worker bound (:342-343).
   No wall-clock lease field; liveness = worker last_seen + 300s reclaim. PERSIST=central_state.json.
   FAIL=WORKER_BUSY+null; None (no match). TEST=upload_flow claim(), windows E2E.
   UNKNOWN=concurrent-claim atomicity beyond RLock single-process (cite V-PKG4-4 residual: -w 1 soft).
5. ATTEMPT — CODE=claim :329-331 (attempts+1, attempt_id, dispatch_id uuid). STATE=task.attempts,
   attempt_id, dispatch_id. PERSIST=central_state.json. ID=`task:attempt:N` + uuid dispatch. FAIL=
   N/A (mint always succeeds). TEST=attempt:2 pin (test_p3:62). UNKNOWN=none.
6. DISPATCH — CODE=claim :327-347 (same response carries TaskPacket). No separate dispatch endpoint;
   no push (pull-only). STATE=status DISPATCHED + worker_id. PERSIST=central_state.json + daemon
   current_task.json CLAIMED (daemon:328-329). ID=dispatch_id. FAIL=prepare_task ContractError→400.
   TEST=claim tests. UNKNOWN=none.
7. EXECUTION — CODE=windows daemon run_task :200-237 (powershell -EncodedCommand, 600s communicate,
   NO kill — orphan, cited). Mac/muse differ (cited MW1-D1). STATE=daemon worker_phase STARTED
   (current_task.json). PERSIST=daemon-local file only. ID=run_id (win: bare PID string :216 —
   weak post-hoc identity, cite W01-T2-2). FAIL=exception→FAILED result; crash→release+HUMAN_REQUIRED
   (never replay :293-297). TEST=daemon E2E executions==[1] pins. UNKNOWN=Mac native/agy paths
   (not re-read; cite MW1).
8. RESULT — CODE=daemon build_result_payload :162-198 (binds 5 IDs + run_id + minted result_id +
   hashed artifacts; FAILED on missing/unsafe/empty evidence) → http_post_result :113-135 (5x backoff
   5xx/transport; 4xx final) → server task_result :352-413. STATE=task.status RESULT_RECEIVED (SUCCESS)
   or QUEUED-retry/FAILED_TERMINAL; task.result=durable. PERSIST=central_state.json; daemon
   RESULT_READY persisted pre-delivery (:335-337). ID=result_id (worker-minted uuid; server checks
   non-empty only — deterministic verify_result result_id NOT used on remote path). FAIL=ACK_DUPLICATE
   (exact 9-field :367-368); 409 terminal-conflict (:369-370) / not-awaiting (:373-374); 400
   Contract/ArtifactError (:380-381). TEST=test_p3:84-118 (ACK/conflict/changed), upload_flow result
   refs. UNKNOWN=none.
9. ARTIFACT — CODE=artifact_store.py put (:85-116, server-hash, claimed-match, atomic blob+record,
   idempotent id) + blueprint upload (:171-198, DISPATCHED-only, binding-echo, name-in-expected) +
   check_reference (:133-144, NO expected_sha256) + daemon upload_artifact/upload_pending (:71-111,
   re-hash-before-upload, OK/REJECTED/UNDELIVERED). STATE=blobs/<sh>/ records/art-*.json under
   COURIER_ARTIFACT_DIR; refs {path,sha256[,artifact_id,size]}. PERSIST=content-addressed files +
   central_state result refs. ID=art-<sha256(material)>. FAIL=400 unsafe/mismatch/over-limit/unknown;
   409 not-DISPATCHED; 413 over-limit; tamper→verifier FAIL. TEST=upload_flow (8 upload/verifier tests)
   + artifact_store unit. UNKNOWN=none on win path.
10. PENDING VERIFICATION — CODE=app.py:456-464 (verifier-auth, status==RESULT_RECEIVED). STATE=tasks
    filter (no separate queue table). PERSIST=n/a (derived). ID=task/result ids echoed. FAIL=401
    wrong key. TEST=pending fetch in upload_flow:132,277. UNKNOWN=none.
11. VERIFY — CODE=verifier verify_artifacts (:54-95) + server /tasks/verify (:466-515: reconciled-
    resend ACK :476-480; independent verifier_id :484-486; result_id+artifacts equality :487-491;
    PASS/FAIL enum :492-494). STATE=task.verification{verifier_id,result_id,verdict,artifacts}.
    PERSIST=central_state.json. ID=result_id equality. FAIL=FAIL→FAILED_VERIFICATION+goal BLOCKED
    (:508-510); 409/400 guards. TEST=verifier 3-way expected test, tamper test, E2E reconcile
    (upload_flow:266-284). UNKNOWN=revenue-lane script behavior (argv call verified, script unread).
12. RECONCILE — CODE=verify PASS branch :503-507 (task RECONCILED, index+1, DONE when plan exhausted)
    + step mirror :511-513. STATE=status + current_step_index + DONE. PERSIST=central_state.json.
    ID=n/a. FAIL=n/a (terminal-good). TEST=step-mirror pin (test_p3:44-49), E2E RECONCILED.
    UNKNOWN=none.
13. DEPENDENCIES — CODE=index gating only (claim :279-281, verify :505). No depends_on/dag (batch
    lane removed). STATE=current_step_index. FAIL=B unreachable until A reconciled (Z06 B-legal
    corroborated). TEST=implicit (single-step goals in tests; multi-step sequencing UNPINNED —
    minor gap, see PKG-C case notes). UNKNOWN=none.
14. READY — NO server READY state (not in TASK_STATES). Daemon-internal "READY" string = upload gate
    (daemon :102/:111/:340-342), never persisted as phase. Do not confuse with wall-slot READY
    (MUSE-NN state.json — different layer, stale DONE/READY relics). TEST=n/a. UNKNOWN=none.
15. AUTO NEXT / B — No push/auto-dispatch; pull-only: daemons poll claim every 10s (daemon :367 loop,
    :321-329 auto-claim when idle). USER_CONTINUE equivalent = 0 manual steps in code path. COST-
    class deferral can idle a claim (silent). TEST=daemon E2E auto-claim. PHYSICAL multi-task A→B
    auto-run unproven (no runner). UNKNOWN=none in code.
16. CONTINUE — No motor/continue process on tree (courier_continue/start_motor zero hits — HARVESTER
    deletion stands). Continuation = daemon loops + verifier loop + watchdog reclaim_stale (server
    :416-454: stale>300s → HUMAN_REQUIRED quarantine, reclaimed always 0, never auto-replay).
    TEST=reclaim single-pin (cite PKG-2). UNKNOWN=watchdog/verifier deployment wiring (scheduled
    tasks — static docs only).

BACKBONE_GAPS (new, owned by BB-01): G-BB1 local-lane expected_sha256 unenforced (see PKG-C case 5 +
 Central Writer input BB01-NEW-1). G-BB2 multi-step A→B sequencing unpinned by any test (code clear,
 zero multi-step test). G-BB3 worker-minted result_id accepted on non-empty only (no determinism;
 safe via 9-field dedupe — INFO, no action).
REFINEMENT (verified 2026-09-27): test_server_integration_contract pins plan SHAPE (planned-a/b
order, index assertions :131-189/:237) and WORKER_BUSY second-claim (:263-293) — but NO test performs
the A→B TRANSITION (reconcile A → head advances → claim returns B). G-BB2 stands as stated.
Docs hygiene (first-hand): docs/p3/README.md STALE — "server needs the three-hunk patch" + "temp copy"
+ "git apply --check is part of that test" are all false on this tree (live code contains the cutover;
p3_preview loads the live file, no git apply). Corroborates V-PKG3-2.
Cited-not-owned: orphan-no-kill (V-PKG1-1), 600-vs-300 lease hole (V-PKG4-3), upload-default-OFF
 (V-PKG3-1), substring match (V-PKG4-1), -w 1 soft (V-PKG4-4), bare-PID run_id (W01-T2-2).
