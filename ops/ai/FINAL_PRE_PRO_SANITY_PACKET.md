# FINAL_PRE_PRO_SANITY_PACKET (PREP 01-10 + 11-25 combo)

CURRENT_HEAD=970eae52 CURRENT_TREE=cdec6030 WORKTREE=357 dirty (foreign active).

PRUNING (nothing deleted, only marked):
REUSE_VALID=turbo4 probe33 ws56 DLQ-03 portable-lock smoke-hist closeout_01-20 turbo_01-10 m-packets g-packets.
SUPERSEDED=iter10 A-to-B note (by committed integration test); turbo_10 BLOCKED (by g-packets); M50-END (by K+freeze packets); PREP_V3-draft (by FINAL_CANNON_BUILD_INPUT_PACKET).
STILL_NEEDED=R1-R4 Google fixes; Windows run; approvals (provider/budget/night/bundle).

EVIDENCE_GRAPH (claim -> proof @candidate):
chain-contract -> turbo-integration 4/4 + probe 33/33 @970eae52.
isolation -> slots/registry/redelivery tests @970eae52.
fail-closed -> controller 21 + transport 3 + adapter 13 @970eae52.
admission -> 100-mix + waves + norm + WHY @970eae52.
context -> 3 builder tests @970eae52. triage -> 50-night tests @970eae52.
Orphaned: none (all packet claims point above).

PREP03 normalization proven (CRLF/BOM/tabs/unicode; JSONL one-line rule).
PREP04 compaction rule: terminal history by reference; active state complete; no evidence deleted; queue truth untouched.
PREP05 frontier: server claim O(N) rescan + full reload per claim; work_queue O(N log N) sort. Suggestion: skip-lists/index (GOOGLE).
PREP06 starvation: no aging found; no incident -> no rule change.
PREP07 blocked pressure: server scans blocked candidates per claim (O(N) cost, GOOGLE note); work_queue filters by READY (efficient); wave-scan measured linear.
PREP08 dead-letter: FAILED_TERMINAL + NOT_REQUIRED elimination exist; no new queue.
PREP09 retry persistence: server retry_state in file-state (by design); work_queue none; controller none (no retries by design).
PREP10 circuit scope: pool:provider lock (server); per-run timeout (adapter); no global kill.

RACE_CANCEL_RESULT=shared-key single child + redelivery (tested, no sleeps).
RACE_PAUSE_DISPATCH=slots sync-atomic, 5-way race one winner (tested).
RACE_UPDATE_DISPATCH=specified (no new exec after safe point); no updater to test.
STORAGE_TRANSACTION_RISKS=server single-save atomicity good; cross-process file race if multi-writer (GOOGLE note).
STORAGE_GROWTH=classify 10k/27ms heap-flat; fixture 14KB/100rec; journal cap 1000; adapter 64k/stream.
LOG_GROWTH=auth-fail debug path writes host file (GOOGLE cleanup note).
RESULT_BACKPRESSURE=timeout caps + PENDING wedge + no auto-retry (measured signals: activeCount, PENDING, BLOCKED).
NIGHT_END_CONDITIONS=no READY->IDLE; limits reached; circuit/resource/storage gates; repeated unknown; explicit STOP; gates branch-only.
RUN_MANIFEST_READY=schema: run_id candidate project input-rev mode provider scopes limits authorization stops created_at (no secrets; no runner yet).
WHY_TRACE_READY=why() 4 lines (tested).
MORNING_TRIAGE_READY=triage.mjs + 50-night tests (deterministic, no LLM).

REUSE_VALID=all green same-candidate proofs. TARGETED_RETEST=none (no relevant code change since runs). STALE_EVIDENCE=none.

GOOGLE_ROOT_CAUSES=R1 turbo asserts+isolation; R2 sync honesty; R3 Windows run; R4 live evidence (+cross-process lock only if multi-writer proven).
PRO_DECISIONS=auto-dispatch vs driver-poll; mode-2 semantics; bundle.
HUMAN_DECISIONS=bundle; night/provider/budget approvals; importer/dispatcher build-or-drop.
UNKNOWN_BLOCKERS=503 source; CLI JSON shape; pricing (none blocks local prep).
NICE_TO_HAVE_LATER=governor metrics; log rotation; 10k import run; mode-3 local.

TESTS_READY=ws56 turbo4 probe33 + committed. TESTS_EXECUTED=this session (exit 0). EXITCODES=0.
READY_FOR_PRO_BUILD=NO (first blocker open).
FIRST_BLOCKER=live + machine evidence. OWNER=GOOGLE.
EXACT_NEXT_ACTION=GOOGLE: R1+R2 fixes, R3 Windows run, STAGE1 approval; then re-evaluate.
