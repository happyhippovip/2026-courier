# FINAL_CANNON_BUILDER_INPUT_PACKET (10/10 final; supersedes earlier draft)

CURRENT_HEAD=970eae52 CURRENT_TREE=cdec6030
OWNERSHIP=ledger/guard/motor+runtime GOOGLE; packets/QA MUSE; physical HUMAN_AND_GOOGLE.
PROVEN_EXISTING=ws-suite 56, turbo 4, probe 33, DLQ-03, portable-lock/smoke-hist, admission/context/triage/slots/adapter builders (all exit 0, same candidate).
MISSING_IMPLEMENTATION=dispatcher/runner, importer, governor metrics, bundle, morning-report-live, updater.

FINAL_MODES=1:1, 2:2, 3:3-local-only. FINAL_PREFETCH<=10 refs.
FINAL_LANE_CONTRACT=1 unresolved/lane; staged admission spec'd, inline-claim today.
FINAL_RESULT_CONTRACT=identity chain; dup/late/redelivery single-effect; tamper rejected.
FINAL_RETRY_CONTRACT=no blind retry; PENDING gate; owner reconciliation; single probe.
FINAL_RESOURCE_CONTRACT=bounds (slots/bytes/timeouts/journal-1000); metrics future.
FINAL_NIGHT_CONTRACT=MODE1, UPSHIFT NO, pinned candidate, branch-only gates, IDLE when empty.
FINAL_UPDATE_CONTRACT=staged, compat-checked, atomic, LKG, build-only rollback.
FINAL_SECURITY_CONTRACT=prompt-is-data; separate approvals; argv-only; no secrets stored.

LOCAL_ACCEPTANCE=ws56 turbo4 probe33 + committed suites (exit 0); missing: importer runs, governor, night sim, update preservation run.
REAL_TEST_LADDER=0 fake done; 1 one harmless task; 2 ten mode-1; 3 small night; 4 full night; 5 mode-2 day; 6 mode-3 later. NOT STARTED.

HUMAN_DECISIONS=bundle; night approval; provider approval+budget; mode-2/3 semantics; dispatcher/importer build-or-drop.
PRO_CANDIDATES=auto-dispatch vs driver-poll; real mode-2 semantics; bundle scope.
UNKNOWN_ITEMS=503 source; real CLI JSON shape; provider pricing.

GOOGLE_ROOT_CAUSES=R1 turbo asserts+isolation (tests/test_turbo_queue*.py; done when green+order-swapped); R2 sync honesty (sync scripts; done when real exits); R3 Windows smoke run (done when exit0+PASS captured); R4 live verify evidence (done when positive+mismatch observed live). Deps: R3 after R2.

READY_FOR_FINAL_GOOGLE_BUILDER_PROMPT=YES
READY_FOR_MODE1_REAL_TEST=NO READY_FOR_NIGHT_RUN=NO READY_FOR_MODE2_LATER=NO
FIRST_BLOCKER=live + machine evidence (GOOGLE).
EXACT_NEXT_ACTION=GOOGLE: fix R1+R2, run R3, approve STAGE1 harmless task; then re-evaluate. No builder/FIRE/Pro prompt written. No providers started. No cannon started.
