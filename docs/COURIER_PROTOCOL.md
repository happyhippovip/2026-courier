# Courier protocol

## Event envelope

Every message uses `courier_event.schema.json`. Version 1 is retained only for
historical records. Version 2 is the canonical GitHub↔Codex envelope and carries
`schema_version`, `message_id`, `task_id`, `correlation_id`, `parent_id`,
`source`, `destination`, `type`, `status`, `created_at`, `payload`,
`payload_hash`, and `max_iterations`. Payloads are small and contain no secrets.

Inbox TASKs are immutable files in `events/incoming/`. A terminal RESULT, ACK,
or BLOCKED message is a separate immutable file in `events/processed/`. The
terminal message records the original `task_id`, `correlation_id`, and its
`parent_id` is the inbox TASK's `message_id`; this makes state transitions
traceable without overwriting a user or courier message.

## Processing rules

1. Validate the JSON envelope before dispatch.
2. Reserve `message_id`; a message already represented by a terminal record in
   `events/processed/` receives no second execution. `payload_hash` is retained
   as a compatible content-level dedupe signal.
3. For a Version 2 TASK, pass `correlation_id` and `task_id` unchanged to its
   worker.
4. Write exactly one terminal RESULT, ACK, BLOCKED, or FAILED record with a new
   `message_id`, the original `task_id` and `correlation_id`, and
   `parent_id=<TASK.message_id>`.
5. Never treat RESULT, ACK, or BLOCKED as a new TASK. This is the echo-protection rule.
6. This bridge test uses `max_iterations=1`. A retry reuses the original
   correlation and task identifiers, but a single run does not prove a general
   exactly-once guarantee.

## Future GitHub trigger

Use **Pull request ready for review** as the preferred trigger. It is explicit,
has a stable GitHub event ID, and avoids the noisy repeated notifications of
comments or generic PR updates. The PR body should contain only a compact
reference: event ID, correlation ID, event type, and dedupe key.

`PR_OPENED` is less suitable because it may fire before the reviewable event
envelope is complete. `PR_COMMENT` is not used for commands because comments
are prone to duplicates and human conversation. `PR_CLOSED` is not a dispatch
trigger.

## Integration boundary

GitHub can be used to trigger Work only after the connector is explicitly
authorized. The Work-to-local return channel must then be proven against the
existing Control Thread with one `COURIER_NOOP_055` roundtrip. Until that test
passes, the normal Chief chat is not considered automatically connected.
