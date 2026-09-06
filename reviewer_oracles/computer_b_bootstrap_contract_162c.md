# Computer B bootstrap acceptance contract — Mission 162C

This reviewer contract is intentionally pre-network and secret-free. A future
physical Node B remains `OFFLINE` until every item below has machine evidence.

## Human boundary

- A human installs software and performs any provider authentication.
- The bootstrap must never copy passwords, 2FA material, browser profiles,
  cookies, OAuth tokens, API keys, or credential stores.
- Autostart may launch only a local verifier; it must not automate login.

## Required fail-closed checks

1. Node ID is unique and is not already active in the durable registry.
2. Node B has a separate writable clone or Git worktree; it must not mount and
   mutate Node A's live writable tree.
3. Repository/project fingerprint and protocol/schema version match the
   dispatcher expectation.
4. Transport is private/LAN-restricted and authenticated. No public `0.0.0.0`
   unauthenticated listener, UPnP forwarding, public unauthenticated tunnel,
   or plaintext credential transport is acceptable.
5. Heartbeat, queue read and result return all have real evidence. Until then
   Node B remains `OFFLINE`/`TRANSPORT_UNAVAILABLE`.
6. A task cannot be executed without a durable matching lease and non-overlap
   file-scope lock.
7. Setup is idempotent: a rerun must preserve existing local work and neither
   reset, clean nor force-checkout a repository.

## Required status vocabulary

`SOFTWARE_MISSING`, `REPOSITORY_MISSING`, `AUTH_REQUIRED`,
`TRANSPORT_UNAVAILABLE`, `READY`, and `OFFLINE` must remain distinguishable.

## Later canary sequence

`PRECHECK → isolated workspace verification → human auth gate if needed →
private transport validation → heartbeat → queue read → no-op leased task →
matched result return → independent oracle comparison`.
