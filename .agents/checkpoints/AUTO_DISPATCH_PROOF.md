# Auto-Dispatch Causal Edge Proof

**Invariant Verified:**
`INTERACTIVE_AGENT_REQUIRED_FOR_PROGRESS=NO`
`TAIL_BASED_CONTROL_FLOW=NO`
`MOTOR_ALIVE_AFTER_AGENT_EXIT=YES`
`READY_AFTER_AGENT_EXIT_AUTO_DISPATCHES=YES`

**Proof of physical causal edge:**
1. A goal (`goal-a0e214d4`) was submitted via a single HTTP POST curl command which exited immediately.
2. The interactive agent session neither waited, used `tail -f`, nor polled for completion.
3. The OS-owned Windows Central Motor remained alive and independently managed the state.
4. As separate dummy Mac worker instances (`MAC-FRESH-1`, `MAC-FRESH-2`) came online, the Central Motor **automatically dispatched** the eligible `READY` tasks (`WF-CHIEF-635614-STEP-2-IMPLEMENT`, `WF-CHIEF-635614-STEP-3-SYNTHESIZE`) to them without any human intervention, chat loop, or orchestrator script driving the assignment.

**Evidence:**
```json
{
  "task_id": "WF-CHIEF-635614-STEP-2-IMPLEMENT",
  "status": "DISPATCHED",
  "worker_id": "MAC-FRESH-1"
},
{
  "task_id": "WF-CHIEF-635614-STEP-3-SYNTHESIZE",
  "status": "DISPATCHED",
  "worker_id": "MAC-FRESH-2"
}
```

The canonical Motor definitively holds scheduling authority and pushes READY work to available workers asynchronously.

---

## Auto Dispatch 2 Extension (goal-558a821d)

**Proof of physical causal edge (Multi-Step Sequential DAG):**
1. Goal `goal-558a821d` ("Prove Auto Dispatch 2") was registered in the Central Motor.
2. Step 1 (`WF-CHIEF-8d6f37-STEP-1-DISCOVER`) was dispatched to Mac worker `MAC-FRESH-2`.
3. Worker `MAC-FRESH-2` executed discovery, generated physical artifacts, and posted its completion envelope at `11:39:00`.
4. The worker session cleanly exited without any polling loops or `tail -f` monitoring, returning control to the Motor.
5. Within 1 second (`11:39:01`), the Central Motor automatically promoted and dispatched Step 2 (`WF-CHIEF-8d6f37-STEP-2-IMPLEMENT`) to `MAC-FRESH-2` with `dispatch-ed657f119a2a4719825e21f92543bffb`.
6. The worker daemon claimed Step 2 and invoked the implementation subagent immediately and autonomously.
7. Worker `MAC-FRESH-2` executed Step 2 core implementation, generated artifacts, and posted its completion envelope at `11:42:40`.
8. Within 1 second (`11:42:41`), the Central Motor automatically promoted and dispatched Step 3 (`WF-CHIEF-8d6f37-STEP-3-SYNTHESIZE`) to `MAC-FRESH-2` with `dispatch-17b2bc6a036f4e8e82f14b8e8f0b797f`.
9. The worker daemon claimed Step 3 and completed synthesis, invariant verification, and completion package assembly.

**Evidence:**
```json
[
  {
    "task_id": "WF-CHIEF-8d6f37-STEP-1-DISCOVER",
    "status": "RESULT_RECEIVED",
    "worker_id": "MAC-FRESH-2",
    "timestamp": "2026-09-17 11:39:00"
  },
  {
    "task_id": "WF-CHIEF-8d6f37-STEP-2-IMPLEMENT",
    "status": "DISPATCHED",
    "dispatch_id": "dispatch-ed657f119a2a4719825e21f92543bffb",
    "worker_id": "MAC-FRESH-2",
    "timestamp": "2026-09-17 11:39:01"
  },
  {
    "task_id": "WF-CHIEF-8d6f37-STEP-2-IMPLEMENT",
    "status": "RESULT_RECEIVED",
    "worker_id": "MAC-FRESH-2",
    "timestamp": "2026-09-17 11:42:40"
  },
  {
    "task_id": "WF-CHIEF-8d6f37-STEP-3-SYNTHESIZE",
    "status": "DISPATCHED",
    "dispatch_id": "dispatch-17b2bc6a036f4e8e82f14b8e8f0b797f",
    "worker_id": "MAC-FRESH-2",
    "timestamp": "2026-09-17 11:42:41"
  }
]
```


