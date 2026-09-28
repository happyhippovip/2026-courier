# Specialist Report K — Pilot Data & Privacy Preparation

**Role**: `PILOT_DATA_PRIVACY_PREP`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  

---

```text
DATA_FLOW_TEMPLATE=
1. Data Categories:
   - Goal Prompts & Task Instructions (user-entered text).
   - Artifact Files (code, markdown reports, text logs).
   - Identity & State Metadata (UUIDs, timestamps, SHA-256 digests, exit codes).
   - Authentication Tokens (local bearer tokens for coordinator API).
2. Provider Involvement:
   - LLM Provider API: Receives task prompt slices and returns completions.
   - Zero telemetry, analytics, or third-party tracking services involved.
3. Storage Location Class:
   - 100% Local-First: server/state/central_state.json, server/state/artifacts/blobs/.
   - Scratch Directory: user-designated local scratch area.
   - Zero central cloud telemetry or remote database synchronization.
4. Permissions:
   - Read/write access strictly bounded to workspace directory.
   - Path traversal (..) and absolute paths outside workspace fail closed (HTTP 400).
5. Retention & Deletion:
   - Retention: Retained until explicit user wipe.
   - Deletion: `courierctl clean --all` purges central state and all artifact blobs atomically.
6. Operator Access:
   - Zero remote operator backdoors. Courier runs as a purely local background service.
7. User-Visible Disclosure:
   - CLI and Web UI display exact file paths where outputs and states are written.

OPEN_COMPLIANCE_QUESTIONS=
- Does the pilot user have proprietary code constraints prohibiting sending snippets to third-party LLM APIs (OpenAI/Anthropic/Google)?
- Should local artifact encryption at rest be enabled for highly confidential client code?

HUMAN_DECISIONS_REQUIRED=
- User confirms selection of local LLM provider API key.
- User approves workspace directory boundary before task execution begins.
```
