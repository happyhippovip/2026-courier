# Context & Token Efficiency Layer

## Core Principles

Courier is designed to orchestrate agentic workflows safely and deterministically. To prevent unbounded provider costs and context exhaustion, Courier mandates the following Token Efficiency principles for all task generation and dispatch:

1. **Context Minimization:** Never send full project or chat history when a bounded task packet is sufficient.
2. **State Authority:** The Repository, canonical goal state, and the durable Ledger are authoritative. Chat history is not required runtime context.
3. **Evidence Reuse:** Prefer diffs and causally relevant files/evidence over full-repository rereads. Reuse still-valid evidence instead of rerunning expensive physical proofs.
4. **Cheapest Sufficient Model:** Always default to the cheapest sufficient model or worker capability for a task.
5. **Escalation Path:** Escalate model capabilities or context size only after execution evidence shows the cheaper attempt was insufficient.
6. **No Background LLM Polling:** Do not use LLMs for active waiting, polling, or monitoring.
7. **No Redundancy Without Purpose:** Avoid duplicate agents solving the same task unless explicitly performing independent verification.
8. **Invariant Preservation:** Token optimization must never weaken physical Acceptance, process safety, worker authority boundaries, or evidence requirements.

## Tracking Metrics

Every dispatched task must track and report the following efficiency metrics:
- `INPUT_TOKENS`
- `OUTPUT_TOKENS`
- `CONTEXT_SIZE`
- `RETRIES`
- `MODEL/WORKER`
- `VERIFIED_TASK_RESULT`
- `TOKENS_PER_VERIFIED_TASK`

*(Note: Provider/account identity remains capacity metadata, never workflow truth).*

## The Minimal Task Packet

Rather than supplying an interactive agent with open-ended conversation history, Courier Motor dispatches work using a strict Minimal Task Packet.

```json
{
  "GOAL_ID": "...",
  "TASK_ID": "...",
  "CURRENT_RUNTIME_SHA": "...",
  "OBJECTIVE": "...",
  "REQUIRED_CAPABILITIES": [],
  "REQUIRED_AUTHORITY": [],
  "RELEVANT_FILES": [],
  "RELEVANT_EVIDENCE": [],
  "ACCEPTANCE_PREDICATES": [],
  "DO_NOT_TOUCH": [],
  "FIRST_CAUSAL_BLOCKER": "...",
  "NEXT_EXECUTABLE_ACTION": "...",
  "CONTEXT_BUDGET": 0
}
```

## Implementation Priority
Implementation of this routing and context-packing layer is strictly prioritized **after publication and pilot readiness**, unless required to remove a current concrete cost bottleneck preventing product acceptance.
