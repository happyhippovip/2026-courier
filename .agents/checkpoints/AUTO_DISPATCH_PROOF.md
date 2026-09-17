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
