# Source Map

BOUND_TO_CODE_HEAD: 7c495f8c1b31293f8d3a5465035d2d3f61cbd3a7
UPDATED_AT_UTC: 2026-09-18

This map is advisory. Revalidate current HEAD before use.

| Component | Known path | Known symbol / note | Status |
|---|---|---|---|
| Server task/result API | `server/app.py` | task claim/result/verification paths have been investigated | VERIFY_ON_USE |
| Motor / frontier execution | `scripts/courier_continue.py` | `execute_task` and frontier/next-action behavior | VERIFY_ON_USE |
| Ledger / Guard | `scripts/agent_handoff_ledger.py` | freshness/update/guard validation paths | VERIFY_ON_USE |
| Mac worker | `scripts/mac_worker/daemon.py` | worker execution + result submission | VERIFY_ON_USE |
| Physical acceptance prep | `scripts/acceptance/prepare_physical_run.py` | physical run plan helper; not proof by itself | CURRENT_HEAD |
| Cockpit server | `scripts/run_visual_studio_server.py` | localhost operations cockpit serving path | VERIFY_ON_USE |
| Cockpit frontend | `studio/` | operations UI / agent telemetry | VERIFY_ON_USE |
| Windows runtime | UNKNOWN | bind process→executable→worktree→SHA before proof | UNKNOWN |

Do not convert a path label into acceptance evidence. Source location and runtime identity are separate facts.
