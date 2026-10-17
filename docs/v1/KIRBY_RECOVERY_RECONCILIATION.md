# Fenced Kirby recovery

An unproven cleanup or a crash during replacement keeps the existing slot
`RECOVERING`, non-accepting, with its workkey pinned. Ordinary wakes, provider
completion lines and restart cannot replay that uncertain operation. Without
trusted reconciliation adapters, the customer state is `NEEDS YOU`.

Every repeated `rotate`/`recover` refusal writes the same complete
`RECOVERY_BLOCKED` receipt shape to `recovery_receipts.jsonl`. No time-based
expiry or force-successor action clears the fence.

## Supported exit

The existing runtime owner registers two synchronous trusted adapters when
constructing `Kirby`; neither adapter nor its authority is loaded from disk:

- `authorize_recovery(context)` returns exactly `True` only when the existing
  permission broker currently covers the actor, host, provider, exact session,
  workkey and consequential recovery action. Its binding must retain current
  authority and fenced ownership through proof and launch.
- `reconcile_recovery(context)` independently refetches current ownership/repo
  truth, proves the predecessor and any ambiguously launched successor have
  stopped, and proves safe continuation will not repeat an uncertain effect.
  It returns `session_id`, integer `token`, `workkey`, `cleanup: "STOPPED"`,
  `still_alive: []`, `resume_safe: true`, and nonempty accepted `evidence`
  references. Provider narration or an absent parent PID is insufficient.

`context` contains snapshots named `session` and `workkey`, plus `actor`.
For a fenced idle slot, `workkey` is `None` and proof names the empty workkey;
resolution makes the slot available without inventing or executing a task.
The adapters must use the existing broker, process-ownership records and
controller/effect reconciliation. They must not invent a new claim system or
accept unchecked proof supplied by a provider.

After those adapters are registered, the authorized control path calls:

```python
kirby.resolve_recovery(
    slot,
    session_id=expected_session_id,
    token=expected_writer_token,
    actor=authorized_actor,
)
```

The exact fence is checked again after the hooks return. Successful resolution
keeps the write-ahead fence through launch, claims the same checkpointed workkey
with a new token, and logs the actor and accepted evidence. A stale/double
resolution cannot launch another successor. Missing authority/proof stays
blocked and produces an audit receipt. Do not edit JSON/SQLite state by hand.

## Evidence boundary

Targeted tests prove scoped refusal, revoked broker grants, lost launch
responses, exact-once resolution, storage-sync failure and real Linux owned
process recovery. The production permission/ownership/effect adapters are not
wired by this component PR; that binding remains with the existing runtime
owner. No Windows-native or live-provider recovery is claimed.
