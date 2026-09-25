# Chief Relay Protocol (Antigravity ↔ Chief / ChatGPT)

## 1. Overview & Objectives

The Chief Relay Protocol provides a deterministic, zero-cost, structured bridge between:
- **Worker (Google Antigravity)**: Autonomous technical execution in pair programming mode, testing, and verified status reporting.
- **Project Lead (Chief Commander in ChatGPT)**: Strategic evaluation of verified results, decision making, and emission of exactly one next command.

This protocol avoids live web-chat push hacks and expensive API polling. It operates asynchronously via structured files stored in this repository or transmitted directly in the user conversation.

---

## 2. Message Lifecycle & Worker Dispatch

```
[CHIEF_NEXT_COMMAND] (Type: COMMAND, Source: chief, Destination: antigravity)
        │
        ▼ (Pushed to GitHub / stored in events/incoming/)
[DISCOVERY & INTAKE] (`scripts/run_chief_relay_cycle.py` discovers pending command)
        │
        ▼
[WORKER JOB BUILDER] (`scripts/build_antigravity_worker_job.py` generates dispatch contract)
        │
        ▼
[STRICT SCHEMA VALIDATION] (Validated strictly against schemas/antigravity_worker_job.schema.json)
        │
        ▼
[EXECUTION HANDOFF] (`events/dispatch/<task_id>-worker-job.json` - WORKER_JOB_READY_FOR_INTERACTIVE_ANTIGRAVITY)
        │
        ▼
[ANTIGRAVITY CONSUMER] (`scripts/consume_chief_command.py` validates scope, cost, gates & dedupe)
        │
        ▼
[SAFE BOUNDED EXECUTION] (Technical execution within allowed scope up to Human Gate)
        │
        ▼
[ANTIGRAVITY_RESULT] (`events/processed/<task_id>-result.json`, Type: RESULT, Source: antigravity, Destination: chief)
        │
        ▼ (Committed & pushed to GitHub)
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

## 4. Hardened Antigravity Worker Job Schema (`schemas/antigravity_worker_job.schema.json`)

Required dispatch fields:
- `schema_version`: `"2.0"`
- `job_id`: Unique identifier (`job-ag-<task_id>-<uuid>`) [Variable metadata]
- `source_command_message_id`: Matching triggering Chief COMMAND `message_id`
- `task_id`: Task identifier
- `correlation_id`: Correlation identifier
- `target_agent`: `"ANTIGRAVITY"`
- `instruction`: Directive extracted verbatim from `one_next_command`
- `allowed_scope`: Strictly authorized repositories (`happyhippovip/2026-courier`, `happyhippovip/2026-project-memory`)
- `forbidden_scope`: List of explicitly prohibited targets (`04-Wellnesskoenig-Website`, `universuX`, `FruitKI`, `2026-Projektzentrale (outside allowed subpaths)`)
- `cost_policy`: Strictly `"ZERO_COST_ONLY"` (`FREE_TIER_ONLY` removed)
- `human_gate_policy`: Strictly `"STOP_ON_HUMAN_GATE_ONLY"` (`AUTO_IF_SAFE` removed)
- `max_iterations`: Strictly `1`
- `expected_output`: Strictly `"ANTIGRAVITY_RESULT"`
- `created_at`: UTC ISO 8601 timestamp [Variable metadata]

### Determinism Definition:
- **Semantic Fields**: Fully deterministic mapping (`instruction`, `allowed_scope`, `forbidden_scope`, `cost_policy`, `human_gate_policy`, `target_agent`, `max_iterations`, `expected_output`, `source_command_message_id`, `task_id`, `correlation_id`).
- **Variable Metadata**: `job_id` (contains random UUID suffix for uniqueness) and `created_at` (runtime timestamp).

---

## 5. Antigravity Result Schema (`schemas/antigravity_result.schema.json`)

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

## 6. Execution & Deduplication Tooling

1. **Cycle Runner**: `scripts/run_chief_relay_cycle.py [--pull] [--push] [--repo-dir <path>]`
   - Scans `events/incoming/` for the oldest pending Chief COMMAND.
   - Invokes `build_antigravity_worker_job.py` to create `events/dispatch/<task_id>-worker-job.json`.
   - Validates the worker job strictly against `schemas/antigravity_worker_job.schema.json`.
   - Invokes `consume_chief_command.py`.
   - Validates the resulting record via `validate_chief_relay.py`.
   - Stages, commits, and pushes the new result if `--push` is supplied.
   - Enforces `max_iterations = 1`.

2. **Worker Job Builder & Schema Validator**: `scripts/build_antigravity_worker_job.py [--command <file>] [--validate-job <file>]`
   - Validates incoming Chief COMMAND envelope, route, hash, hardened scope, and policies.
   - Emits canonical `antigravity_worker_job` in `events/dispatch/`.
   - Validates emitted jobs directly against `schemas/antigravity_worker_job.schema.json`.

3. **Consumer**: `scripts/consume_chief_command.py --command <file> [--incoming-dir <dir>] [--processed-dir <dir>]`
   - Enforces schema, route, type, hash, scope, cost policy, human gate policy, and `message_id` deduplication.
   - Generates and writes `events/processed/<task_id>-result.json`.

4. **Validator**: `scripts/validate_chief_relay.py --file <file> [--incoming-dir <dir>] [--processed-dir <dir>]`
   - Deterministic standalone validator for results and commands.

---

## 7. Deduplication & Echo-Protection Rules

1. **No Echo**: A RESULT cannot be consumed as a new TASK/COMMAND.
2. **Deterministic Hash**: Payloads with mismatched `payload_hash` are rejected.
3. **Idempotence**: `message_id` is the primary deduplication key. Events already in `events/processed/` must never be executed twice.
4. **Lineage Reference**: `parent_id` serves as a provenance link and does not block distinct events with new `message_id`s.
5. **Single-step bounded**: `max_iterations = 1` ensures each run completes one discrete cycle without uncontrolled recursion.
