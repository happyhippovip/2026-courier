# P5: Product Extensions (Communities & Chats) - Package Definition

This document describes the prioritized packages for the Courier P5 phase, adhering to the requirement to avoid building a new parallel architecture around the core orchestration engine. All features will be implemented as standard Goals, Tasks, and Server State extensions within the existing Courier `server/app.py` and `Motor` framework.

## 1. Package: Profilanzeige (Profile Display)
**Description:**
Extends the existing Worker and User identity models to support public-facing profiles. This allows Courier participants (both human operators and agentic workers) to have a visible identity, capabilities list, and historical execution statistics.
- **Core Integration:** Adds a `/users/<id>` and `/profiles` endpoint to `server/app.py`. Uses the existing state serialization (`@serialize_state_mutation`).
- **Acceptance Criteria (Abnahme):**
  - A REST API endpoint successfully returns a combined profile of a worker's capabilities and historical task completion rate.
  - No new database engines are introduced; state remains in `central_state.json`.
  - Profile data is read-only for unauthenticated users, writeable only by the owner or system orchestrator.
- **Cost Considerations (Kostenbetrachtung):**
  - **Storage:** Minimal JSON size increase (~1-2KB per profile).
  - **Compute:** Low overhead, basic CRUD operations.
  - **Budget:** ~0.00 EUR additional infrastructure cost.

## 2. Package: Gruppenentdeckung (Group Discovery)
**Description:**
A registry mechanism that allows agents and users to discover existing groups, namespaces, or specialized worker pools. This enables dynamic routing of tasks to specialized communities instead of hardcoded worker IDs.
- **Core Integration:** Expands the `required_capabilities` routing logic in `claim_task` to support `required_groups`. Groups are just tags applied to workers and users in the central state.
- **Acceptance Criteria (Abnahme):**
  - A goal can be submitted with `"required_groups": ["researchers"]`.
  - Only workers registered with the `researchers` group tag can claim the task.
  - A discovery endpoint `/groups` lists all active groups and their current online worker count.
- **Cost Considerations (Kostenbetrachtung):**
  - **Storage:** Negligible.
  - **Compute:** Slight increase in routing latency during `claim_task` (O(N) tag matching), but negligible for <1000 workers.
  - **Budget:** ~0.00 EUR additional infrastructure cost.

## 3. Package: Communities
**Description:**
Logical containers that bundle Profiles, Groups, and Goals together into shared organizational units (e.g., "Courier Open Source Community", "Internal Enterprise X"). Goals submitted within a Community are sandboxed to workers within that Community.
- **Core Integration:** Adds a `community_id` field to the Goal schema. The dispatcher (`_worker_is_eligible`) will enforce that the worker's `community_id` matches the goal's `community_id`.
- **Acceptance Criteria (Abnahme):**
  - A worker from Community A cannot claim a task from Community B, even if capabilities match.
  - Community administrators can view all goals and tasks within their community.
  - Fails closed: If `community_id` is missing, it defaults to a global public pool (or requires explicit isolation depending on deployment strictness).
- **Cost Considerations (Kostenbetrachtung):**
  - **Storage:** ~100 bytes per goal/worker for the ID.
  - **Compute:** One additional string comparison during dispatch.
  - **Budget:** ~0.00 EUR.

## 4. Package: Chats (Synchronous Communication)
**Description:**
A lightweight messaging channel tied to specific Goals or Communities, allowing workers (agents) and humans to exchange context, request clarification (`HUMAN_REQUIRED`), or broadcast status updates without bloating the formal `agent_handoff_ledger.json`.
- **Core Integration:** Adds a `/goals/<goal_id>/chat` endpoint appending messages to a `chat_history` list in the Goal state.
- **Acceptance Criteria (Abnahme):**
  - Agents can POST a message to a Goal's chat stream.
  - Humans can POST a reply.
  - The chat is strictly scoped to the lifecycle of the Goal; when the Goal is achieved and archived, the chat is archived with it.
  - No external WebSockets required initially; long-polling or simple REST GET is sufficient to avoid parallel architecture.
- **Cost Considerations (Kostenbetrachtung):**
  - **Storage:** Can grow rapidly. A strict limit of 100 messages per goal, or 10KB per goal, must be enforced to prevent `central_state.json` from becoming too large to serialize efficiently.
  - **Compute:** High read volume if clients poll aggressively.
  - **Budget:** Potential need for a larger VM if polling frequency saturates the single-threaded Flask server. Estimated <5 EUR/month scale-up cost if traffic spikes.

## 5. Package: Plattformverbindungen (Platform Connections)
**Description:**
Webhooks and OAuth integrations allowing Communities to link out to GitHub, Discord, or Slack for notifications and federated identity.
- **Core Integration:** Uses the existing HTTP adapter pattern (like `providers/tiktok_provider.py`). Adds a `webhooks` array to the Community state. When a Goal reaches `RECONCILED`, the server fires a background HTTP POST to the registered webhooks.
- **Acceptance Criteria (Abnahme):**
  - When a Goal completes, a JSON payload is successfully delivered to a mock webhook endpoint.
  - Timeout and retry logic for webhooks fail cleanly without crashing the main server thread.
- **Cost Considerations (Kostenbetrachtung):**
  - **Storage:** Negligible.
  - **Compute:** Network I/O wait times. Must be executed in a background thread to prevent blocking the Flask event loop.
  - **Budget:** Egress bandwidth costs (negligible at pilot scale).
