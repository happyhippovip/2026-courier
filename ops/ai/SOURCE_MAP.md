# SOURCE_MAP — verified component locations
BOUND_TO_CODE_HEAD: 7c495f8c1b31293f8d3a5465035d2d3f61cbd3a7
UPDATED_AT: 2026-09-18T00:15:00+02:00

RESULT_INGESTION: COMPONENT=result_feed FILE=scripts/run_visual_studio_server.py FUNCTION=handle_api_state ROLE=aggregates events for cockpit BOUND_TO_CODE_HEAD=7c495f8c
TASK_CLAIM: UNKNOWN
TASK_RESULT: UNKNOWN
VERIFICATION: COMPONENT=acceptance tests FILE=tests/test_courier_continue.py ROLE=physical-proof gating BOUND_TO_CODE_HEAD=7c495f8c
RECONCILIATION: COMPONENT=frontier recompute FILE=scripts/courier_continue.py FUNCTION=main ROLE=stateless recompute from PROVEN_EDGES BOUND_TO_CODE_HEAD=7c495f8c
QUEUE_MOTOR: COMPONENT=motor loop FILE=scripts/courier_continue.py FUNCTION=main/compute_frontier/execute_task BOUND_TO_CODE_HEAD=7c495f8c
AUTO_REPLENISHMENT: COMPONENT=frontier recompute FILE=scripts/courier_continue.py FUNCTION=main ROLE=no manual refill BOUND_TO_CODE_HEAD=7c495f8c
CHECKPOINT_CURSOR: COMPONENT=atomic ledger write FILE=scripts/agent_handoff_ledger.py FUNCTION=atomic_write/update ROLE=fsync+rename, revision fencing, no separate cursor BOUND_TO_CODE_HEAD=7c495f8c
WAITING_PROVIDER: COMPONENT=capability filter FILE=scripts/courier_continue.py FUNCTION=compute_frontier ROLE=provider-wait stays local BOUND_TO_CODE_HEAD=7c495f8c
WORKER_IDENTITY: COMPONENT=heartbeat endpoint FILE=server/app.py FUNCTION=heartbeat ROLE=worker_id registration BOUND_TO_CODE_HEAD=7c495f8c
RUNTIME_SHA: COMPONENT=runtime truth FILE=scripts/runtime_truth.py ROLE=ACTUAL_SERVING_RUNTIME_SHA observation BOUND_TO_CODE_HEAD=7c495f8c
ACCEPTANCE_GUARD: COMPONENT=guard derivation FILE=scripts/agent_handoff_ledger.py FUNCTION=update ROLE=prior-evidence-only acceptance BOUND_TO_CODE_HEAD=7c495f8c
LEDGER_WRITE: COMPONENT=ledger update FILE=scripts/agent_handoff_ledger.py FUNCTION=update/initialize BOUND_TO_CODE_HEAD=7c495f8c
WINDOWS_RUNTIME: COMPONENT=windows observer OWNER=Google FILE=scripts/studio_local_tools.py ROLE=hosts.windows runtime_sha observation BOUND_TO_CODE_HEAD=7c495f8c
COCKPIT_TELEMETRY: COMPONENT=state endpoints FILE=scripts/run_visual_studio_server.py FUNCTION=handle_api_state/handle_api_local_tools ROLE=/api/state + /api/local-tools BOUND_TO_CODE_HEAD=7c495f8c
