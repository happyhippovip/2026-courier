# Autonomous Agent Capability, Skill & Handoff Architecture

## 1. Overview & Architectural Principles

This document formalizes the **Capability + Skill + Handoff + Safety Layer** for the 2026 Courier system (Mission 113).

Our design integrates modern persistent-agent architectural patterns (such as durable identity, governed skills, connector boundaries, and resumable human intervention) as **general engineering concepts**. It contains **no proprietary implementation, cloned code, or external dependencies**.

---

## 2. Concept Mapping: General Ideas $\rightarrow$ Our Implementation

| General Industry Concept | Our Concrete Courier Implementation | Design Principles & Safeguards |
| :--- | :--- | :--- |
| **Persistent Agent Identity** | `AgentProfile` & `AgentProfileRegistry` in `scripts/capability_registry.py` | Durable local agent metadata (`agent_id`, `role`, `capabilities`, `memory_scope`). **Zero secret storage**: API tokens, keys, and credentials are strictly rejected/redacted. |
| **Action Safety & Guardrails** | `ActionSafetyClass` & `SafetyPolicyEvaluator` | Strict classification: `READ`, `WRITE`, `PUBLISH`, `DELETE`, `PAYMENT`, `IDENTITY`, `AUTH`. `DELETE` is denied by default; `PUBLISH`, `PAYMENT`, `AUTH` require Human Gates. |
| **Governed Tool Capabilities** | `CapabilityRegistry` | 21 canonical capabilities (`LOCAL_FILES_READ`, `SAFE_SHELL`, `VIDEO_PRODUCTION`, etc.) with fail-closed state tracking (`AVAILABLE`, `UNAVAILABLE`, `AUTH_REQUIRED`, `APPROVAL_REQUIRED`). |
| **Reusable Workflows & Skills** | `SkillRegistry` | Grounded strictly in verified existing implementations (`LOCAL_CANARY_VERIFY`, `REVIEW_BUDGET_EVALUATE`, `CONTEXT_PACKAGE_BUILD`, `COURIER_TASK_TRANSPORT`, `COURIER_RESULT_TRANSPORT`). |
| **Learned Routines** | `RoutineProposalSystem` | Observed successful workflows produce `RoutineProposal` artifacts in `PROPOSED` state. Never automatically approved without explicit human/Chief decision. |
| **Agent Collaboration & Delegation** | `HandoffProtocol` & `HandoffMessage` | Multi-agent task transfers where `task_id` and `correlation_id` are strictly preserved across handoffs. Physical routing visualized via Courier. |
| **Minimal Shared Context** | `MinimalContextTransferEngine` | `UNCHANGED_CONTEXT_RESEND = FORBIDDEN`. Identical snapshot hashes use reference links; modified states transmit lightweight deltas only. |
| **Tool / Service Connectors** | `ConnectorRegistry` | Explicit connector metadata (Local FS, Git, GitHub, X, YouTube, TikTok, Gmail, Calendar) with fail-closed authentication states (`AUTH_REQUIRED`). |
| **Resumable Human Intervention** | `ResumableHumanGateManager` | Standardized gates (`LOGIN`, `OAUTH`, `2FA`, `CAPTCHA`, `PAYMENT`, `PUBLICATION`, `DESTRUCTIVE_ACTION`). Workflows pause and resume with intact identities. |

---

## 3. Detailed Component Specifications

### A. Action Safety Policy
Every tool operation is verified before dispatch:
- **READ:** Allowed if capability state is `AVAILABLE`.
- **WRITE:** Allowed under local policy controls.
- **PUBLISH:** Dispatches to `PUBLICATION_GATE` (Human approval required).
- **DELETE:** Hard-denied (`DENY_BY_DEFAULT`).
- **PAYMENT / IDENTITY / AUTH:** Dispatches to specific Human Gate (`PAYMENT_GATE`, `IDENTITY_GATE`, `AUTH_GATE`).

### B. Agent Profile Security Invariant
Agent profiles are persistent configurations stored locally. The registry enforces strict regex scanning:
```python
SECRET_PATTERNS = [
    r"(?i)(password|passwd|pwd)",
    r"(?i)(secret|token|bearer|api[_-]?key|auth[_-]?code)",
    r"(?i)(private[_-]?key|ssh[_-]?key)",
    r"(?i)(credit[_-]?card|cvv|iban)",
]
```
Any payload containing secrets is immediately rejected with a security violation.

### C. Agent Handoff Protocol
When a task crosses capability boundaries (e.g. Research $\rightarrow$ Builder):
1. Source agent packages `HandoffMessage`.
2. Router verifies target agent's capabilities.
3. Courier physically transports the envelope (`📦 HANDOFF`) to the destination desk.
4. Target agent executes while preserving `task_id` and `correlation_id`.

### D. Resumable Human Gate Lifecycle
```
[Workflow Running] -> [Encounter Sensitive Gate (e.g. OAuth / Payment)]
       │
       ▼
[Action Stopped] -> [task_id / correlation_id Preserved] -> [Gate Exposed to Human]
       │
       ▼
[Human Verification / Approval] -> [Workflow Resumes without ID Mutation]
```

---

## 4. Verification & Grounding

All capabilities, skills, and connectors defined in this architecture are verifiable locally:
- 0 paid model calls for registry evaluation or motion state resolution.
- Deterministic test coverage in `tests/test_capability_registry.py`.
- Full alignment with Walking HQ telemetry in `studio/execution_truth.js`.
