# T10 RESULT — Test-gap map (static reference analysis, read-only)

MODE: shell-less LIGHT. Method: for each source module, searched tests/ for
references by module basename. "GAP" = zero test references (direct or by path).
A test could theoretically cover a module without naming it, so verdicts read
as "no direct reference", not "provably untested". No tests executed (no shell).

## Gaps (no direct test reference)

G-T10-1 (MEDIUM) scripts/courier_watchdog.py — BEHAVIOR UNTESTED.
Only 1 hit in tests/: a filename in a contract list in
test_server_integration_contract.py:95 (auth-env check, not behavior).
The watchdog is the 3rd process in the motor start path (T8 map); its
restart/escalation behavior has no deterministic test. Owner: motor scope.

G-T10-2 (MEDIUM) scripts/orphan_task_reaper.py — DEAD-CODE CANDIDATE.
Zero test refs; zero importers/callers repo-wide (only a comment mention in
windows_update_manager.py:36 + egg-info SOURCES). Content is mock-ish
(hardcoded ui_handles, relative state paths). Owner decision needed:
revive+test or archive. No action taken here.

G-T10-3 (LOW) scripts/queue_processor.py — WRAPPER ERROR PATH UNTESTED.
Thin CLI over intake_dispatcher.dispatch_intake (dispatch itself IS covered
by test_intake_dispatcher_state_guards). Untested: the bare
`except Exception: print(...)` swallow path (no durable blocker record) and
the sys.path/CWD-dependent `from intake_dispatcher import` (same family as
the T6 scripts-packaging gap). Owner: intake scope.

G-T10-4 (LOW) scripts/revenue_v1_safety_baseline.py — INDIRECT ONLY.
Zero direct test refs; exercised only indirectly when integration/torture
tests spawn courier_verifier (which shells out to it, courier_verifier.py:71).
A verifier-invoked safety baseline deserves direct unit tests. Owner: revenue scope.

G-T10-5 (LOW) scripts/first_run.py + scripts/update_courier.py — UNTESTED.
Zero refs. Health-check runner + migration runner = installer/updater paths
with no tests. Owner: setup/update scope.

G-T10-6 (INFO) Ops/tooling modules with zero refs (owner to triage):
studio_local_tools.py, task_routing.py, worker_contract.py, support_bundle.py,
log_rotation.py, validate_courier_task.py, windows_crash_recovery.py,
windows_repair_mode.py, windows_update_manager.py.
NOTE: test_routing_acceptance_v1.py exists but never names task_routing —
it covers a different routing layer; task_routing.py itself is unreferenced.

## Hygiene note
tests/test_DLQ02_freshness_bound.py.bak — a .bak file inside tests/.
Dead weight in the test tree; owner to remove or restore. Not touched here.

## Well-covered (direct refs observed, spot-checked)
ledger (10+ suites), courier_continue, motor (crash/DLQ04/eligibility),
server (integration/schema/retry), provider_hub, provider_wait x2,
queue_independent x2, result_duplicates, result_identity_binding,
retry_contract, restart_resume_torture, operating_ledger, intake_dispatcher,
revenue_worker_adapter, runtime_truth, trust_boundary, security_hygiene,
daemon_secret_hygiene, mac_worker (hygiene/torture/boundaries),
windows daemon/worker/wall/supervisor/launcher/safe-slot, github x2,
youtube x2, human_gate, global_queue_stall, zero_hang, courier_verifier
(spawned in integration + torture tests).

## Disposition
Read-only mission: NO TESTS WRITTEN (MUSE lane allows tests/** writes, but
RC planning is FROZEN and nothing is executable without shell — authorship
without execution would be unverified; left as packet-grade gap list).
G-T10-1..6 handed to writer owners. No files outside runtime/slots/MUSE-45 touched.
