# Courier Canonical Bootstrap

To start or resume Courier execution autonomously as a fresh authorized worker without previous chat history or context pasting:

```bash
python3 scripts/courier_continue.py --run
```

## Architecture Invariants

* **Motor** = sole runtime scheduler, eligibility/claim and execution authority.
* **Ledger** = durable coordination, evidence and zero-chat handoff. Never a scheduler or queue.
* **Execution Plan** = `COURIER_AUTONOMOUS_EXECUTION_PLAN.md` defines roadmap and routing policy.
* **Canonical Ledger Location** = `agent_handoff_ledger.json`.
* There is one canonical Motor-controlled executable frontier. Do not create per-provider, per-machine, Antigravity, Mac, Windows or CLI queues.

## Universal Worker Contract

Mac Antigravity, Windows Antigravity, Google CLI and future authorized workers use the same contract. Each worker identifies its host/OS/interface, capabilities, authorities, available resources, owned scopes and availability. Tasks declare required capabilities, authority, resource scope, acceptance predicates and minimal context. Motor matches tasks to eligible workers; provider identity is metadata, not workflow truth.

Default routing preference is deterministic tool/script first, bounded CLI for mechanical work, Antigravity for reasoning-heavy work, and another authorized worker when it is the better eligible fit or the preferred worker is unavailable/insufficient. This is a preference, not a hardcoded provider dependency.

Workers do not ask the human where a discovered subtask should go. They submit/record the bounded task through the existing Motor mechanism with its capability/authority/resource requirements. Motor decides the claim. One writer owns a logical scope/resource at a time; independent scopes may run concurrently.

After a verified task completes, the worker checkpoints the result and immediately recomputes/claims the next eligible task. A human `continue` message is not part of normal execution.

On session/quota/worker loss: checkpoint, push, clean owned processes, canonically yield/release when safe, and let Motor recompute eligibility. Never bypass ownership, automate account rotation, or circumvent provider limits.

## Minimal Task Packet

Workers receive only the smallest durable context required: `GOAL_ID`, `TASK_ID`, `CURRENT_RUNTIME_SHA`, `OBJECTIVE`, `REQUIRED_CAPABILITIES`, `REQUIRED_AUTHORITY`, `RELEVANT_FILES`, `RELEVANT_EVIDENCE`, `ACCEPTANCE_PREDICATES`, `RESOURCE_SCOPE`, `DO_NOT_TOUCH`, `FIRST_CAUSAL_BLOCKER`, `NEXT_EXECUTABLE_ACTION`, `CONTEXT_BUDGET`. Raw chat history is not runtime context when canonical state is sufficient.

## Durable Restart & Machine Reboot

Courier uses the existing Motor/OS-service process-ownership infrastructure for deterministic recovery. OS/provider background facilities may wake/start the canonical continuation path but must not decide task ownership themselves.

* **Machine reboot / worker crash**: restart the canonical Motor/continuation path using the supported OS service mechanism and reconstruct from durable state.
* **Terminal/session ends**: agent sessions are disposable; checkpoint/yield cleanly.
* **Fresh worker**: run `python3 scripts/courier_continue.py --run`; no old chat reconstruction.

## Night Mode Safety

Unattended execution consumes every eligible safe/free/reversible task and pivots around scope-local blockers. It must not auto-spend, sign up payment providers, perform prohibited unattended merges, bypass credentials/security controls, send unauthorized external sales messages, fabricate evidence/PASS, or perform destructive broad cleanup.

Optimize for verified completed work per worker-minute/token using deterministic execution, minimal context, hash/diff-first inspection and valid evidence reuse. Never trade acceptance quality or safety for token savings.
