# Chief Relay Protocol (Antigravity <-> Chief / ChatGPT)

## 1. Overview & Objectives

The Chief Relay Protocol provides a deterministic, zero-cost, structured bridge between:
- **Worker (Google Antigravity)**: Autonomous technical execution, testing, and verified status reporting.
- **Project Lead (Chief Commander in ChatGPT)**: Evaluation of verified results, decision making, and emission of exactly one next command.

This protocol avoids live web-chat push hacks and expensive API polling. It operates asynchronously via structured files stored in this repository or transmitted directly in the user conversation.

---

## 2. Message Lifecycle

```
[CHIEF_NEXT_COMMAND] (Type: COMMAND, Source: chief, Destination: antigravity)
        │
        ▼
[ANTIGRAVITY EXECUTION] (Autonomous execution within allowed scope up to Human Gate)
        │
        ▼
[ANTIGRAVITY_RESULT] (Type: RESULT, Source: antigravity, Destination: chief)
        │
        ▼
[CHIEF EVALUATION & NEXT COMMAND] (Chief reads facts, decides safe next state)
```

---

## 3. Envelope Specification (Courier v2.0)

Every event uses the canonical v2 envelope:
- `schema_version`: `"2.0"`
- `message_id`: Unique ID (e.g. `msg-ag-<task_id>-<uuid>` or `msg-chief-<task_id>-<uuid>`)
- `task_id`: Unique task identifier
- `correlation_id`: Global workflow/pipeline correlation identifier
- `parent_id`: For a RESULT, must be the TASK/COMMAND's `message_id`. For an initial COMMAND/TASK, `null`.
- `source`: `"antigravity"` (for results) | `"chief"` (for commands)
- `destination`: `"chief"` (for results) | `"antigravity"` (for commands)
- `type`: `"RESULT"` | `"COMMAND"`
- `status`: `"DONE"` | `"NEW"` | `"FAILED"` | `"BLOCKED"`
- `created_at`: UTC ISO 8601 timestamp
- `payload`: Structured JSON object conforming to specific schema
- `payload_hash`: SHA256 hex digest of canonical payload JSON (`json.dumps(payload, sort_keys=True, separators=(',', ':'))`)
- `max_iterations`: Exactly `1`

---

## 4. Antigravity Result Schema (`schemas/antigravity_result.schema.json`)

Required payload fields:
- `source_agent`: `"ANTIGRAVITY"`
- `summary`: High-level summary of action performed
- `verified_facts`: Array of verified empirical facts (paths, hashes, test outputs)
- `files_changed`: Non-negative integer count of modified files
- `commits`: Array of commit hashes / descriptions
- `test_results`: Summary of local automated test executions
- `cost`: Cost incurred (must be `0.00 EUR` / zero cost)
- `human_gate`: Description of any blocking human gate (or `"NONE"`)
- `safe_next_state`: Clear status recommendation for the Chief

---

## 5. Chief Command Schema (`schemas/chief_command.schema.json`)

Required payload fields:
- `target_agent`: `"ANTIGRAVITY"`
- `one_next_command`: Clear, unambiguous technical directive
- `allowed_scope`: Array of allowed paths / tasks
- `human_gate_policy`: `"STOP_ON_HUMAN_GATE_ONLY"`
- `cost_policy`: `"ZERO_COST_ONLY"`

---

## 6. Deduplication & Echo-Protection Rules

1. **No Echo**: A RESULT cannot be consumed as a new TASK/COMMAND.
2. **Deterministic Hash**: Payloads with mismatched `payload_hash` are rejected.
3. **Idempotence**: A `message_id` that has already been processed and recorded in `events/processed/` must never be executed twice.
4. **Single-step bounded**: `max_iterations = 1` ensures each run completes one discrete cycle without uncontrolled recursion.
