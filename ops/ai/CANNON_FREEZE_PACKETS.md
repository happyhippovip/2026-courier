# CANNON FREEZE PACKETS 1-9/10 (HEAD 970eae52, TREE cdec6030)

## CANNON_ARCHITECTURE_FREEZE_PACKET
CURRENT_HEAD=970eae52 CURRENT_TREE=cdec6030
REUSED_COMPONENTS=server queue+contract; work-script controller/adapter/slots/triage/admission/context (56 tests); turbo tests (4); probe chain (33).
CANONICAL_QUEUE=server file-state (prod) + work_queue file-state (tooling).
CANONICAL_DISPATCHER=none (driver-claim only; no second scheduler built).
CANONICAL_RESULT_PATH=result->verify->release, single atomic save, dup-ACK.
CANONICAL_UPDATE_PATH=none (manual sync scripts only).
CANONICAL_CONTROLLER=work-script OFF/pulse/journal/fail-closed.
MODES=1:1, 2:2, 3:3-local-only-until-proven. PREFETCH<=10 refs. LANE_CONTRACT=1 unresolved per lane. RESULT_FIRST=yes. UNKNOWN_EFFECT=PENDING no retry. ONE_WRITER=enforced (claim serial, slots sync, registry). NO_SECOND_SCHEDULER=yes. NO_SECOND_LEDGER=yes.
ARCHITECTURE_BLOCKERS=dispatcher missing (decision); importer missing (decision).

## CANNON_IMPORT_ADMISSION_FREEZE_PACKET
IMPORT_FORMATS=TXT/JSONL, one record/line, streaming required (no impl yet).
STREAMING=required, unproven (no importer). RESUME=import_id+source-fingerprint+index+checkpoint (spec). REIMPORT=same identity, no dup. RECORD_IDENTITY=(project,text). TASK_FORMATION=explicit id or derived identity; multi-record same task allowed if same need.
ADMISSION_GATES=project/scope/capability/deps/approval/no-running-dup/no-reusable-result/no-gate (admission.mjs).
INVALID_HANDLING=too-large/broken/missing-text -> INVALID with reason.
HUMAN_DECISION_HANDLING=no-approval/self-privilege -> HUMAN_DECISION, never auto.
SCALE_10K=classifier proven to 10k/27ms; importer unrun. SCALE_1M_STATUS=local-param-only, never live.
GOOGLE_FIXES_REQUIRED=none unless staged pipeline decided (then server states).

## CANNON_FEEDER_LANE_FREEZE_PACKET
PREFETCH=<=10 refs. MODE1=1 external lane. MODE2=2 independent lanes (fake-proven). MODE3=3 local-only.
LANE_STATES=AVAILABLE RESERVED SUBMITTING RUNNING RESULT_PENDING BLOCKED OUTCOME_UNKNOWN (contract; server subset implemented).
MAX_UNANSWERED=1. ONE_WRITER_ENFORCEMENT=claim serial + write-scope leases + slots.
UNKNOWN_HANDLING=lane stays locked, PENDING, no retry.
ADAPTER_PATH=supported CLI/API exec adapter (stub-proven); no personal-window automation.
REAL_LANE_EVIDENCE=none. LOCAL_LANE_EVIDENCE=overlap/race/slots/probe (fake).
BLOCKERS=dispatcher; real approval.

## CANNON_RESULT_RECOVERY_FREEZE_PACKET
TASK_BINDING=chain goal/task/attempt/dispatch/execution/worker enforced, mismatch rejected. ATTEMPT_BINDING=stale attempt cannot overwrite (DLQ-03). EXECUTION_BINDING=run/execution_ref part of identity.
DUPLICATE=one logical effect (ACK paths). LATE=current kept. LOST_ACK=redeliver stored result, no re-execution.
UNKNOWN_EFFECT=reconcile before retry (PENDING gate). CRASH_BEFORE_PERSIST=nothing stored, resend safe. CRASH_AFTER_PERSIST=single-save atomicity.
RESTART=DONE stays DONE; READY kept; RUNNING reconciled truthfully; PAUSED/CIRCUIT/retry-counts/next-start kept.
PAUSE_PERSISTENCE=yes (journal). CIRCUIT_PERSISTENCE=PENDING (no auto-retry).
GOOGLE_FIXES_REQUIRED=cross-process file locking if multi-writer proven needed.

## CANNON_BACKPRESSURE_RESOURCE_FREEZE_PACKET
429=respect Retry-After; no parallel surge (server pool lock exists; adapter maps class).
503=no start avalanche (fail-closed + PENDING). TIMEOUT=kill-own + partial kept+marked.
CIRCUIT=persistent pause; single probe after owner reconciliation.
PROBE=max one, then MODE1 only.
RESOURCE_GREEN=chosen mode. YELLOW=no extra lane, prefetch may shrink. RED=no new task, pause.
AUTO_DOWNSHIFT=3->2->1->PAUSE only. AUTO_UPSHIFT=NO.
PAUSE=no new starts. STOP=orderly, restart OFF. EMERGENCY=exact own pids only.
PROCESS_OWNERSHIP=registry required. BLOCKERS=governor metrics unimplemented (bounds only).

## CANNON_NIGHT_FREEZE_PACKET
NIGHT_DEFAULT=MODE1 MAX_ACTIVE_EXTERNAL=1 UPSHIFT=NO.
AUTHORIZATION_CONTRACT=project/import, scopes, data destination, provider, attempt/storage limits, stop conditions (schema in manifest; no runner yet).
STOP_CONDITIONS=AUTH/PAYMENT/STORAGE_UNSAFE/BINDING_BROKEN/REPEATED_UNKNOWN/RESOURCE_RED/UNRECOVERABLE/local STOP.
CONTINUE_CONDITIONS=eligible READY + free lane + budget + green/yellow resources.
HUMAN_GATE_BEHAVIOR=branch-only blocking. IDLE_BEHAVIOR=no READY -> IDLE, no polling loops.
MORNING_REPORT=STARTED DONE FAILED BLOCKED HUMAN_GATE UNKNOWN 429 503 CIRCUIT RESOURCE REMAINING NEXT READY NEEDS_HUMAN UPDATE (measured only; builder: triage.mjs).
UNKNOWN_FIELDS=stay UNKNOWN. FIRST_BLOCKER=night runner + approvals (HUMAN/GOOGLE decision).

## CANNON_UPDATE_FREEZE_PACKET
BUILD_IDENTITY=commit+tree+os+built_at+smoke (test-build-identity pattern).
UPDATE_CORE=check->stage->build->smoke->verify identity->compat->activate->verify loaded.
UPDATE_LOCK=single updater, dirty tree blocks.
STAGING=separate test checkout (exists, behind). SMOKE=queue smoke (Windows pending).
STATE_COMPATIBILITY=schema check before activate; DONE never back to READY; no full reimport.
ATOMIC_ACTIVATION=single switch; LKG kept. ROLLBACK=app build only, never repo reset.
QUEUE_PRESERVED=yes REQUIRED. RESULTS_PRESERVED=yes. CIRCUIT_PRESERVED=yes. IMPORT_PRESERVED=yes.
NIGHT_UPDATE_BEHAVIOR=detect, defer to safe point, never disrupt unknown effect.
BLOCKERS=honest-exit sync fix (G2); Windows run (G3).

## CANNON_SECURITY_FREEZE_PACKET
PROMPT_IS_DATA=yes (admission control-patterns -> HUMAN; argv-no-shell; no text->permission).
PERMISSION_BOUNDARY=grant-gated; text cannot grant. PROVIDER_BOUNDARY=separate approval. BUDGET_BOUNDARY=separate approval. WRITE_SCOPE_BOUNDARY=leases + registry.
SHELL_SAFETY=argv arrays only (tested vs injection). SECRET_SAFETY=none stored/logged (journal test).
RESULT_AUTHORITY=verifier role + binding (server); adapter marker (local).
SECURITY_TESTS=no-interp, approval/cwd/flag gates, artifact shape, priv-esc fixture.
FINDINGS=none open in own scope. GOOGLE_FIXES_REQUIRED=none.

## CANNON_FINAL_LOCAL_ACCEPTANCE_PACKET
CURRENT_HEAD=970eae52 CURRENT_TREE=cdec6030
IMPORT=SPEC-only. ADMISSION=100-mix green. PREFETCH=bounds only.
MODE1=fake green. MODE2_LOCAL=fake green. MODE3_LOCAL=missing.
RESULT_FIRST=green. DUPLICATES=green. LATE_RESULT=green. RESTART=partial (controller green, server foreign).
429=partial. 503=green. CIRCUIT=behavioral green. RESOURCE=bounds only.
HUMAN_GATE=partial. STOP=green. UPDATE=not done. SECURITY=green (own scope).
NIGHT_FAKE=missing (no runner). MORNING_REPORT=builder green, no live night.
TESTS=ws56 turbo4 probe33 DLQ03 portable-lock/smoke-hist. EXITCODES=all 0.
REUSED_EVIDENCE=all above (same candidate, no STALE).
FAILURES=none red. GOOGLE_FIXES_REQUIRED=G1 turbo asserts, G2 sync honesty, G3 Windows run, G4 live evidence.
READY_FOR_BUILDER_FREEZE=YES (packet-wise). FIRST_BLOCKER=live+machine evidence. OWNER=GOOGLE.
