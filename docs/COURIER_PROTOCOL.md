# Courier protocol

## Event envelope

Every message uses `courier_event.schema.json` and carries a stable
`event_id`, `correlation_id`, `task_id`, and SHA-256 `dedupe_key`. Payloads are
small and contain no secrets.

## Processing rules

1. Validate the JSON envelope before dispatch.
2. Atomically reserve `dedupe_key`; a duplicate receives no second execution.
3. Pass `correlation_id` and `task_id` unchanged to the existing Switchboard
   and Control Thread.
4. Store the terminal result as `FINAL_REPORT` or `ACK` with the original
   correlation ID and the original event ID as `payload.parent_event_id`.
5. Never treat a result as a new command. This is the echo-protection rule.
6. Retries reuse the same `event_id`, `correlation_id`, and `dedupe_key`.
   A retry may resume a pending delivery but may not re-run a processed task.

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
