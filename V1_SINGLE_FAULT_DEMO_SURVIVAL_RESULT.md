```
V1_SINGLE_FAULT_DEMO_SURVIVAL_RESULT
FAULT_INJECTION_METHOD: SIGTERM (kill -15) during REAL_INDEPENDENT_IMPLEMENTATION
EFFECT_COUNT_BEFORE_FAULT: 1
SURVIVAL_SUCCESS: TRUE
DUPLICATION_PREVENTED: TRUE
MINIMAL_FIX_APPLIED: TRUE (Patched FounderModePlanner.discover_and_plan & evaluate_success for deduplication)

DEMO_EMERGENCY_ACTION
If Courier crashes during the demo, restart the exact same process (using `python3 scripts/courier_founder_mode.py --goal "YOUR_GOAL_HERE"`). The patched queue manager will pick up the orphaned ACTIVE goal, and the updated discovery/planning phase will deduplicate existing physical effects (preventing duplicate writes) and securely transition the goal to SATISFIED. No manual task routing is needed.
```
