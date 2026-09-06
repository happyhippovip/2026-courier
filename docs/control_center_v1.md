# Control Center V1 - Operator Guide

## Architecture
The Local Control Center V1 (`scripts/control_center.py`) provides deterministic visibility into the Courier autonomy state. It is a strictly read-only script that pulls reality from three canonical event stores:
1. `events/founder-mode/goals.json`
2. `events/mission-queue/queue.json`
3. `events/worker-availability/fingerprints.json`

## Real Autonomy Constraints
- **Zero Simulation:** The board strictly outputs the reality of the underlying JSON stores. No hard-coded demo data is used for missions or goals.
- **Health Rules:** Re-enforces strict invariants: Uptime alone never triggers a RED restart; known workloads (like heavy builds or model evaluations) are excluded from idle alarms; and a second quiet-window confirmation is required before escalating to a RED state.

## Operator Usage
To view the current Courier state:
```bash
./scripts/control_center.py
```

This will display the active Founder Goals, Mission Queue, Writer/Worker identity footprints, HUMAN_GATE blockers, and output the computed Next Safe Action.
