# T10 RESULT — Repo-wide test→module gap map (static, read-only)

DELTA NOTE (dedupe): pre-existing T10_test_gaps.md (basename-reference deep dive:
watchdog static-only, orphan_reaper dead-code w/ caller audit, queue_processor
swallow path, revenue_v1 indirect, first_run/update) is CANONICAL for those six.
This file is the tier map (import-line + subprocess evidence, 96 units).
METHOD CAVEAT: "ZERO" = no import/subprocess/static-pin trace; modules may still
be named in strings/comments (e.g. mac_worker/daemon.py in a run_boundaries
finding string; launch_visual_studio.py in snitch-audit fixture strings).
CORRECTION-2 (supersedes): mac_worker.daemon is DIRECT-HYGIENE-ONLY —
test_daemon_secret_hygiene.py:25-27 imports it via importlib.reload and exercises
load_config/write_log. Daemon behavior loop still untested (see G-T10-3).

MODE: shell-less LIGHT. Method: import-line evidence in all 4 styles tests use
(`from scripts.x`, `from scripts import x`, bare `import x`/`from x` via sys.path,
importlib file-location) + subprocess-launch refs + static source/path pins.
Claims OBSERVED unless marked. Wall .ps1 static gaps already in
TESTGAP_dedupe_stale.md §2 — not duplicated here.

## Inventory (OBSERVED)
- pytest files: 72 tests/test_*.py containing "def test".
- Manual runners: tests/acceptance/soak_test.py (*_test.py name: collected, 0 tests;
  live 50-goal soak when run directly), tests/boundaries/run_boundaries.py (not
  collected), scripts/windows_muse_wall/soak_test.py.
- Other: tests/test_execution_truth.mjs (node), test_DLQ02_freshness_bound.py.bak
  (DISABLED, reason UNKNOWN), conftest.py + *.json fixtures.
- Implementation mapped: 82 scripts/*.py + 12 scripts/*/*.py + server/app.py +
  server/run_waitress.py = 96 units. (providers/dashboard/tools noted, not mapped.)

## Tiers
DIRECT-IMPORT 29: agent_handoff_ledger, agent_session_manager, attestation_contract,
courier_continue, courier_github_dispatcher, github_worker_adapter,
inbound_response_observer, intake_dispatcher, integration_contract, invoice_generator,
operating_ledger (importlib), publish_youtube_package, resource_policy,
revenue_worker_adapter, run_autonomous_loop, run_bodyguards, run_chief_commander,
run_codex_bridge, run_snitch_watchdog, run_thought_ingestion, run_thought_memory_mesh,
run_visual_studio_server, runtime_truth, windows_muse_wall.supervisor,
windows_muse_wall.slot_state, windows_worker.daemon, mac_worker.daemon (hygiene only), provider_hub.hub, server.app.
SUBPROCESS-BEHAVIORAL 1: courier_verifier (launched live by test_auto_replenishment
+ test_tomato_two_torture; env contract pinned by test_server_integration_contract).
STATIC-ONLY 2 (+ps1 per TESTGAP §2): courier_watchdog (script path + API-key env
pinned by test_server_integration_contract:93-95,95; no behavioral run observed),
windows_muse_wall.watcher (1 static assertion, TESTGAP).
INDIRECT-WEAK 3 (top-level-imported by DIRECT modules; incidental only):
run_antigravity_bridge, run_context_sync, run_thought_curator.
ZERO 60: 54 top-level + 6 subdir + server/run_waitress.py. Top-level:
account_switch, apply_memory_update_proposal, build_antigravity_worker_job,
build_channel_workflow_tasks, build_handoff_package, build_memory_update_proposal,
cleanup_handler, consume_chief_command, customer_status, customer_status_view,
entitlement_boundary, evaluate_memory_proposal_for_auto_approval,
execute_p01_transmission, export_data, feed_evidence, first_run,
gemini_worker_adapter, human_gate_ux, launch_visual_studio, log_rotation,
mac_worker_adapter, orphan_task_reaper, patch_retries, product_health_check,
publish_courier_result, queue_processor, rc_builder, register_social_channel,
render_godot_movie, resolve_project_memory, revenue_customer_intake,
revenue_v1_safety_baseline, run_academy, run_academy_demo, run_batch,
run_chief_relay_cycle, run_content_production_pipeline, run_demo_workflow,
safe_repair, stack_inspector, start_motor, start_opportunity_daemon (BROKEN import,
see T11), start_verifier, studio_local_tools, submit_goal, support_bundle,
task_routing, update_courier, validate_chief_relay, validate_courier_task,
windows_crash_recovery, windows_repair_mode, windows_update_manager,
worker_contract. Subdir: acceptance.prepare_physical_run,
acceptance.run_final_acceptance, mac_worker.health_check,
windows_muse_wall.soak_test, windows_worker.stop_safe, windows_worker.worker_status.

## Headline gaps (no test trace at all)
G-T10-1 (HIGH) SAFETY CORE UNTESTED: queue_processor, task_routing,
worker_contract, validate_courier_task, safe_repair, orphan_task_reaper,
submit_goal — dispatch/routing/contract/safety-net modules with zero coverage.
G-T10-2 (HIGH) ACCEPTANCE HARNESS ITSELF UNTESTED:
acceptance.prepare_physical_run + run_final_acceptance have no tests; a bug in
the prover is invisible by construction.
G-T10-3 (MEDIUM) MAC WORKER PARTLY UNTESTED: mac_worker.daemon DIRECT for
secret-hygiene only (test_daemon_secret_hygiene via importlib.reload:
load_config/write_log); register/heartbeat/claim loop untested; health_check ZERO.
G-T10-4 (MEDIUM) SERVICE STARTERS UNTESTED: start_motor, start_verifier ZERO
(verifier covered only as subprocess; motor starter not at all).
G-T10-5 (LOW) Test-to-test imports: test_queue_independence.setup_ledger reused
by test_ledger_false_green_attack + test_restart_resume_torture — collection
coupling; helper belongs in conftest/helpers. Owner cosmetic.

## Out of scope but observed
providers/youtube_provider.py DIRECT (2 youtube tests). dashboard/server.py +
tools/courierctl coverage NOT audited here. server/run_waitress.py ZERO (P3-adjacent
installer artifact; P3 read-only respected).

## Disposition
Read-only: NO TESTS ADDED (shell down — new tests unrunnable/unverifiable this
session; writing unrun tests risks fake green). Gaps handed to writer owners.
No files outside runtime/slots/MUSE-45 touched.
