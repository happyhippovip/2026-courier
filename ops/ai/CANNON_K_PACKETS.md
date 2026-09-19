# CANNON K PACKETS (K06-K14, one file, delimited sections)

## CANNON_ADMISSION_PACKET
CURRENT_ADMISSION_PATH=server claim decides inline (QUEUED+deps+eligibility+quota+busy, single save); work_queue READY+priority+write-scope leases. No staged CLASSIFIED/ELIGIBLE states exist.
MISSING_GATES=staged pipeline states; explicit scope/capability registry; idempotency key on submit.
LOCAL_RULES=work-script/admission.mjs classify(): 7 verdicts; identity=(project,text); control-text->HUMAN; dup->REUSE; unknown-dep->NEEDS_CONTEXT; unmet-known-dep->WAIT; missing approval->HUMAN; oversize/broken->INVALID.
AMBIGUOUS_CASES=unknown dep (NEEDS_CONTEXT, not INVALID); same text other project (distinct READY); in-flight dup (REUSE join).
FIXTURES=admission100.fixture.json (100: 10/30/15/15/14/8/8 across 7 verdicts; READY=30<100); night-project.fixture.json (12, expectations pre-fixed).
GOOGLE_DELTA=IF a staged pipeline is wanted: add CLASSIFIED/ELIGIBLE/ADMITTED states server-side (decision, not built here).
FIRST_BLOCKER=none for local rules; staged gates need HUMAN/GOOGLE decision.

## CANNON_DEPENDENCY_PACKET
GRAPH_CURRENT=server depends_on membership per claim scan; work_queue reconcile on DONE; batch seq deps.
CYCLE_HANDLING=self/unknown deps unproven; no cycle detector found (NOT_APPLICABLE without incident).
LAZY_EXPANSION=firstWave(graph, done, maxInitialWave=4): wave/deferred/suppressed; done work never rescheduled; result-covered plans suppressed.
UNNEEDED_TASK_SUPPRESSION=suppressedByResult + done-set; tested.
TEST_FIXTURES=cases A+B->C, chain, fan-in, blocked+independent, suppression, 5-planned->2-first, 50-queued cap=4.
GOOGLE_CHANGE_REQUIRED=none proven; cycle detector only on incident.

## CANNON_CONTEXT_PACKET
MINIMUM_CONTEXT_FIELDS=TASK_ID GOAL EXACT_TASK INPUT_REVISION ACCEPTANCE READ_SCOPE WRITE_SCOPE RELEVANT_FILES RELEVANT_RESULTS KNOWN_CONSTRAINTS DO_NOT_REPEAT EXPECTED_OUTPUT.
CURRENT_REUSE_PATH=none (no packager existed); now context-packager.mjs (refs+hashes only).
STALE_CONTEXT_DETECTION=recordedHash compare -> stale flag.
OVERSIZED_CONTEXT_RISK=file>cap -> reference-only, never hashed (hard cap 1MB).
FIXTURES=3 tests (exact/thin/bloated: missing+stale flagged, 5 irrelevant dropped).
GOOGLE_DELTA=none (app-side utility).

## CANNON_THROUGHPUT_PACKET (/tmp/bench_k09.mjs, one run, fake records)
classify: N=100/1.5ms, 1000/5.7ms, 10000/27.1ms (~3-15us/rec, heap flat).
wave-scan: 100/0.3ms, 1000/0.3ms, 10000/1.7ms (linear).
MODE1_LOCAL_RATE=classify-bound ~35k rec/s (not Muse speed). MODE2/MODE3_LOCAL_RATE=same classifier (no separate engine).
BOTTLENECK=server claim rescans all goals/tasks + full file reload per claim O(N) (GOOGLE hotspot); work_queue sorts O(N log N).
RESULT_BACKLOG_THRESHOLD=none observed locally <=10k; backlog rule: result-slower-than-starts => brake starts (policy, not yet wired).
MEMORY_OBSERVATION=flat for classify; fixture JSON 14KB/100rec.
GOOGLE_OPTIMIZATION_NEEDED=claim-path index/skip-lists for blocked candidates; only if proven slow.

## CANNON_EVIDENCE_INVALIDATION_PACKET
FINGERPRINT_FIELDS=code hash, input revision, policy version, package version, build identity, adapter version, config.
REUSE_RULES=15-entry map (evidence-map.fixture.json): UI/text/logo -> NO_EFFECT.
INVALIDATION_RULES=parser/adapter/retry/timeout/journal/claim -> TARGETED path retest; verify/ledger/schema -> FULL_PATH; scheduler -> NEW_ACCEPTANCE.
TARGETED_RETEST_MAP=in fixture (change -> suites).
OVERTEST_RISKS=rerunning everything per prompt; directory-runner quirk mistaken for failure.
UNDERTEST_RISKS=reusing ledger proof after contract change; Mac-green as Windows-proof.

## CANNON_ADAPTER_CONTRACT_PACKET
CURRENT_ADAPTERS=exec-adapter (spawn, argv-only, CWD allowlist, approval gate, timeout/kill-own, cancel-by-id, redelivery, error classes); README existing-session contract (no backend).
COMMON_INTERFACE=start/run/cancel + result{status,reason,errorClass,exitCode,output-capped,marker,ids} + ERROR_CLASSES[10].
PROVIDER_SPECIFIC_FIELDS=command/argv, verifier keys, quota pools (stay outside common core).
ERROR_MAPPING=success/timeout/auth/payment/malformed/cancelled/unknown/blocked/exit (stub modes auth/payment/partial/fail/slow).
RESULT_MAPPING=COMPLETE iff exit0+marker; else INCOMPLETE/TIMEOUT/ABORTED/BLOCKED with reason.
MISSING_ABSTRACTIONS=real CLI JSON shape; quota/price signals.
GOOGLE_DELTA=none (app-side contract).

## CANNON_SAFE_STOP_PACKET
PAUSE_SEMANTICS=new starts stop; admitted running work finishes per contract (controller: stop() never kills accepted work).
STOP_SEMANTICS=orderly halt; restart stays OFF (tested); PENDING journal persists.
EMERGENCY_SEMANTICS=exact own processes only (adapter cancel by execId+pid; unknown refused); no pkill/killall; no foreign sessions.
PROCESS_OWNERSHIP_REQUIRED=registry execId->pid + task/attempt binding.
RESTART_BEHAVIOR=OFF after restart; no silent resume; PENDING reconciled by owner.
TEST_FIXTURES=stop-idle/running/inspect-race/restart-OFF/PENDING (controller suite).
GOOGLE_FIX_REQUIRED=none (server stop paths foreign, unexamined).

## CANNON_STORAGE_PACKET
CURRENT_STORAGE_PATHS=journal localStorage (cap 1000); tmp file-state; server JSON state; logs.
UNBOUNDED_OUTPUT_RISKS=server result bodies unbounded shape-checked only; fixed by caps below.
PREVIEW_STRATEGY=adapter maxBytes 64k/stream + truncated flag; context fileCap + hard 1MB no-hash.
DISK_GUARD=journal-full blocks; low-disk start-gate NOT implemented (rule only).
WRITE_FAILURE_BEHAVIOR=storage throw -> zero dispatch (tested); timeout partial kept+marked.
CLEANUP_RULES=tmp dirs removed after use (smoke/probe); no log rotation implemented.
GOOGLE_DELTA=result-body size cap + log rotation (if proven needed).

## CANNON_MORNING_TRIAGE_PACKET
RAW_RESULTS=50 synthetic (34 done, mixed gates/fails/unknown/reused/reviews).
GROUPED_ITEMS=DONE34 FAILED4 BLOCKED4 HUMAN_GATE2 UNKNOWN1 REUSED3 REVIEW3.
NEEDS_HUMAN=auth-expired, quota-empty, secret-request, timeout-ambiguous, delete-archive, exit-3, unknown-cause (rank order).
ROOT_CAUSE_GROUPS=7 causes. DUPLICATE_ALERTS_SUPPRESSED=6 (1+3+2).
NEXT_READY=READY_CANDIDATE ids only (admission list).
GOOGLE_DELTA=none.
