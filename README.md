# Courier

> **The durable runtime for work that outlives the AI session.**

Courier is an open-source orchestration runtime designed to separate the interactive AI agent (the *Planner*) from the execution environment (the *Motor*). 

Today's AI agents live and die with the chat window. If a script crashes, a provider hits a rate limit, or the user closes their browser, the context is lost. Courier solves this by securely persisting goal state and seamlessly routing tasks to replaceable worker processes—meaning your agentic workflows can survive crashes and interruptions without requiring human "continue" prompts.

## Key Capabilities

- **Zero-Touch Worker Replacement:** If a worker node crashes mid-task, Courier's Motor safely preserves the exact state and assigns a replacement worker to resume the job.
- **Session Persistence:** Execution is completely decoupled from the UI. Work continues overnight or through network drops.
- **Independent Verification:** A detached Verifier process cryptographically or deterministically validates output evidence before work is marked complete.
- **Durable Agent Handoff:** Native support for zero-chat ledger handoffs between different specialized interactive agents.

## Quickstart (Local Demo)

You can run our standalone, self-contained demonstration to see Courier handle a simulated worker crash and recovery.

```bash
# Clone the repository
git clone https://github.com/your-org/courier.git
cd courier

# Run the local orchestration demo
python3 demo/local_demo.py
```

*Note: The demo uses mock local worker processes to simulate a distributed execution environment without requiring complex network configuration.*

## Architecture

Courier operates on a strict **Capability → Authority → Collision** routing model:
1. **Goal Submission:** You or your LLM Planner submits a declarative `workflow_plan`.
2. **Motor State:** The Courier Motor writes the state to a durable local ledger (`server/state/`).
3. **Dispatch:** Replaceable worker processes pull tasks based on their reported capabilities.
4. **Recovery:** If a worker heartbeat fails or a process dies, the task is marked as retryable and safely handed to the next available worker.
5. **Reconciliation:** The independent Verifier confirms task artifacts before advancing the workflow DAG.

For deep technical details on the internal engine design, see [`docs/INTERNAL_ARCHITECTURE.md`](docs/INTERNAL_ARCHITECTURE.md).

## Pilot Program & Commercial Support

Are you building multi-step agentic workflows that suffer from fragile scripts, LLM timeouts, or session loss? 

We are currently running an Early Access Pilot. Bring us one existing agentic workflow, and we will integrate it with the Courier Motor on your own infrastructure to demonstrate durable execution.

**[Read the Pilot Program Details](docs/PILOT_PROGRAM.md)**

## Contributing

Courier is an open-source community edition. We welcome issues, pull requests, and architecture discussions. Before contributing, please ensure any modifications pass the canonical physical acceptance test.

## License

This project is licensed under the [MIT License](LICENSE).
