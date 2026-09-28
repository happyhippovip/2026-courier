# MAC-FINISH-08 — Zero-Human Relay Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-08
- **Area**: ZERO_HUMAN_RELAY_PACKET
- **Status**: COMPLETE

Establishes the autonomous handoff proof: transition from Task A -> Verification -> Task B -> Completion occurs with zero human intervention.

---

## 2. Invariant Contract
- `HUMAN_RELAY_COUNT = 0`
- Zero interactive prompts (`input()`, readline, modal dialogs)
- All transitions driven exclusively by HTTP API state changes and automated scheduler.

---

## 3. Autonomous Handoff Flow
1. Worker A finishes Task A -> Submits result to `/tasks/result`.
2. Server detects submission -> Calls automated verifier hook.
3. Verifier audits artifact hash -> Emits `VERDICT: PASS`.
4. Server marks Task A `RECONCILED`.
5. Scheduler checks dependency graph -> Finds Task B (`dependencies: ["canary-task-a"]`) now unblocked -> Sets Task B to `READY`.
6. Worker B polling loop immediately claims Task B.
