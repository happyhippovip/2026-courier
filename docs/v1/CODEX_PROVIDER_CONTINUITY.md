# Codex provider continuity — bounded component contract

This extends `scripts/provider_circuit.py`, `provider_hibernation.py` and
`provider_survival.py`. It does **not** start Codex, install a wake source,
alter LaunchAgents, switch accounts or buy credits. The legacy Muse/Gemini
simulation path is preserved; it is not evidence of live provider execution.

## Enablement boundary

`CourierScheduler(primary_provider="codex", state_path=...)` requires durable
state. Codex is registered but unauthorized by default. Supply the explicit
connection roster from the existing authorized registry, with capabilities,
provider family and authority scopes. Different accounts of the same family
are not automatic fallback targets. Authorization is never restored from disk.

Required trusted production hooks:

- `probe_provider(connection_id, capability, timeout_s)` returns `(ok, code,
  message)`. Enforce the supplied 5-second I/O deadline in the existing bounded
  connector/worker runtime. Never implement this callback as an unbounded model
  turn. The scheduler performs at most one call per consumed recovery episode;
  it does not spawn a timeout thread or detached process.
- `refresh_repository(checkpoint)` **fetches** current repository truth and
  returns `repo_sha`, `branch`, and optionally `pr`. A cached historical SHA is
  not an implementation of this contract. Failure aborts dispatch.
- `reconcile_ownership(checkpoint, truth)` returns a context manager holding the
  existing fenced mutable-scope lease, or `None` when another writer owns it.
  Check current canonical PR ownership as well as the runtime lease. Inside the
  guard, yield `workkey`, `mutable_scope`, freshly derived `next_units`, and
  `next_action`. Old NEXT instructions are discarded, not blindly replayed.
  Keep the lease/fencing check valid through execution, including remote writes.
- `authority_check(provider, task, checkpoint)` validates current grants,
  capability/effect/privacy constraints through the existing permission broker.
  Return exactly `True` only if covered. `is_authorized=True` alone is not enough.
- `execute_provider(provider, task, checkpoint)` and
  `execute_local(task, checkpoint)` execute bounded units under those grants.
  Return `{"status": "DONE", "evidence": [accepted_evidence_reference, ...]}`
  only after independent acceptance. Returning from a probe is NOT task success.
  Quota/rate-limit responses may carry a trusted datetime `reset_time` and
  `no_effect=True` only when the connector has positive evidence that execution
  did not begin. Otherwise the started unit stays effect-uncertain.

These hooks are deliberately not inferred from names or connected automatically.
The repository currently has no live caller wiring this scheduler to Codex's
desktop quota events. `scripts/` is also outside the packaged V1 distribution.
Component tests therefore do not establish deployed/app-level auto-resume.
Shipping requires the existing runtime owner to bind these hooks, consume the
wake boundary and expose the component through its supported packaged entrypoint.
Do not introduce a second daemon or broaden package scope by installing all legacy scripts.

## Durable behavior

`record_provider_failure(checkpoint, code, message, reset_time=...,
retry_after=...)` accepts trusted connector failure metadata. The snapshot
contains the exact workkey, branch/SHA/PR, effect/dispatch identity, evidence,
completed fingerprints, pending task descriptors, circuits and started markers.
It is atomically replaced and fsynced before resource release and before probe
or execution. The existing worker-home OS lock protects each read/update/wake;
this is not a shell wall/claim job and creates no background process. Give a
logical continuation one stable state path, not one path per window. Corrupt or
incompatible snapshots fail closed. Do not put credentials or prompts containing
secrets in checkpoint fields.

If a connector also supplies newer progress, pass `expected_checkpoint` containing
the exact previously read checkpoint dictionary. Comparison and replacement happen
under the same runtime owner lock. A stale comparison or attempted scope/connection/
authority retarget is refused without changing the saved snapshot. Already accepted
fingerprints and evidence references are retained. A changed checkpoint without this
comparison is rejected rather than silently discarded. Duplicate failure metadata
for otherwise identical progress needs no checkpoint replacement.

Register only proven-owned release/reacquire hooks on `LaneHibernator`.
Hooks must be idempotent and verify process identity, not executable name.
Release failures remain visible; resource acquisition failures are not swallowed.
After restart, hooks must be explicitly re-registered; they are never deserialized.

`next_wake_at()` supplies one reset boundary for the **existing** authorized wake
source after state has been loaded by failure handling or a wake. No reset means
no timer. Duplicate wakes coalesce under the owner lock. A claimed probe is saved
before the call. Failure consumes the old reset and parks again. A crash during
the probe leaves its claim in flight, conservatively requiring fresh authorized
availability/reconciliation rather than resending an ambiguous probe.

A successful probe permits reconciliation, not immediate mutation. Repository
refresh precedes lease reconciliation, reacquisition and execution. Independent
LOCAL_READY work can continue through its bounded executor/ownership guard while
Codex is unavailable. Compatible, differently-family fallback still requires a
current grant. Missing connectors/checks do not fake completion.

Execution is write-ahead marked. A crash between execution and accepted evidence
leaves an uncertain unit parked; a duplicate wake cannot replay it. External
effect reconciliation remains with the existing controller/human-authority path.
Accepted fingerprints are not discarded to keep an arbitrary rolling history small.

## Proof boundary

Offline tests: `tests/test_codex_provider_continuity.py` (stdlib unittest,
Python 3.12), plus existing provider survival, hibernation and wake-coalescing
tests. No account, network, provider process, payment API or timer is exercised.
Injected lease/fetch/connector tests prove ordering and refusal contracts, not
that the desktop application or a real connected provider already honors them.
