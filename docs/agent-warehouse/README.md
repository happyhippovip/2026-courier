# Courier Symphony — Agent Warehouse

Status: bootstrap catalog for Issue #120.

This directory is the durable inventory and selection contract for Courier agents, provider bridges, specialist roles, and reserve workers.

It is **not** a spawn list. An agent appearing here does not authorize another process, window, provider call, mutable writer, or paid action.

## Selection principle

Choose the smallest safe capable owner for the current task.

Order of decision:

1. exact current gate / required capability;
2. current mutable ownership and duplicate check;
3. required host / OS;
4. authority and side-effect class;
5. cheapest already-authorized capable provider/model (Issue #118);
6. provider availability / continuity state (Issue #119);
7. lowest sufficient reasoning effort;
8. reserve Bodyguard only when the normal specialist is unavailable and capability match is proven.

## Canonical rules

- One logical mutable scope = one writer.
- Do not create a new agent because a prompt arrived.
- UI presence is not proof of runtime capability.
- Historical docs are evidence, not current truth.
- Machine/runtime evidence outranks names, avatars and old status files.
- STANDBY reserve workers do not consume model capacity.
- Provider/model selection must not silently increase spend.
- Provider interruption must preserve continuation truth.
- Windows-native evidence comes from Windows; macOS-native evidence comes from macOS.
- Unknown authorization fails closed.

## Current inventory groups

### Core coordination

- `agent-chief-commander`
- `smart-resource-router`
- `agent-human-gate-monitor`
- `agent-thought-curator`
- `agent-update-steward`
- `agent-courier-relay`
- `agent-snitch`
- `agent-memory-mesh`
- `agent-test-guardian`
- `agent-loop-supervisor`

### Learning / specialist

- `agent-academy-teacher`
- `agent-academy-director`
- `agent-asset-validator`
- `agent-video-synth`
- `agent-channel-dispatcher`

### Provider / execution

- `agent-antigravity-bridge`
- `agent-codex-bridge`
- `worker-google`
- `worker-codex`
- Muse runtime under `scripts/mac_worker/`

### Reserve

Eight Bodyguards, Alpha through Hotel, managed by `scripts/run_bodyguards.py`.

They are reserve slots. They are not eight permanently active model workers.

## Current gaps to evaluate

These are gaps to evaluate, **not automatic permission to create new agents**:

- first-class Claude provider bridge;
- unified provider/model selector, preferably by extending Smart Resource Router;
- unified provider continuity across Muse/Google/Codex/Claude, Issue #119;
- generic real-adapter/content-source role, initially driven by the crypto-news migration in Issue #112.

Before a new agent is added, prove that an existing owner cannot absorb the durable responsibility cleanly.

## Files

- `AGENT_CATALOG.json`: machine-readable bootstrap inventory.
- `SELECTION_POLICY.md`: routing and escalation contract.

Runtime code must not consume this catalog as authoritative until schema validation and tests are added.
