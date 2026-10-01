# Provider Handoff & Failure Isolation Spec

## GQ43: Provider Handoff & Task Identity
The identity of a task and its resulting evidence must be completely decoupled from the specific AI provider (Google, Muse, Sonnet, Opus, Codex) that executes it.

- **Task Identity (task_id):** Generated independently by the Courier Server.
- **Provider Capability:** Workers register with generic capabilities (e.g., `["github", "python", "unix"]`). The server assigns tasks to *capabilities*, not *specific providers*.
- **Worker Identity (worker_id):** A unique GUID for the instance of the physical worker process, unrelated to the LLM backend.
- **Result Binding:** The result payload includes a generic `provider` field (`provider: "mac_physical"`) but the Courier verifier hashes the *content* of the execution (the diff, the test results, the artifact), not the name of the LLM.

This guarantees that a task partially executed by Claude (Sonnet) can be handed off, if it fails, to an instance powered by Google (Gemini) simply by Courier re-queueing the task.

## GQ44: Provider Failure Isolation
Courier must not halt if a specific AI provider's API goes down.

1. **Timeout & Dead-Letter Queue:** If a worker claims a task but fails to return a result within the `POLL_INTERVAL_SECONDS` * max retries (due to a provider API 500 or timeout), the task is moved back to `PENDING` state.
2. **Dynamic Re-assignment:** The Courier Server will automatically hand the task to the next available worker polling the queue. If Worker A (using OpenAI) is failing, Worker B (using Google) will successfully claim and execute it.
3. **No Global Block:** Provider-specific connection code MUST be contained entirely within the individual worker scripts (or the AI IDE extension), NEVER in `courier_verifier.py` or `integration_contract.py`. The core engine does not know what an LLM is; it only knows Tasks and Results.
