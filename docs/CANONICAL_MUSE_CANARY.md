# Canonical Muse wall convergence

Base: `supervisor/canonical-muse-runtime` at
`823172e9c53551bbec5c94e4f46bfc550cca6058`. This extends the existing
`scripts/mac_worker/muse_supervisor.py` / `daemon.py` / `muse_adapter.py` path.
No historical screen wall, competing supervisor, or main changes are required.

## First physical execution: exactly one bounded canary

From this branch's checkout, run **only**:

```sh
python3 scripts/mac_worker/muse_supervisor.py canary
```

This is the one-slot equivalent of START 1: one logical canary slot, one `muse exec`,
60-second ceiling, no task claim, no automatic restart, no Keychain lookup, no
`--yolo`, no external job queue. It always supplies
`--workspace /Users/user/Downloads/2026-courier`, independent of shell cwd.
It uses the same production adapter, durable prompt, STOP fence, current Mac
resource checks, execution runner and owned-child cleanup as normal slots.
The prompt asks only for a connectivity response, not file changes or tool use.
No physical canary is executed by the automated test suite.

It refuses a held supervisor lock, STOP, unresolved existing slot ownership, or
unreadable/unsafe resources. Evidence lives at `<wall>/canary/01/state/`.
An existing RESULT_READY is reported without executing again. An ambiguous
STARTED is blocked for operator reconciliation. Never delete evidence to retry.

## Only remaining physical CLI boundary proof

The operator has observed `exec`, `resume`, `session-message`, `--workspace`,
`--reasoning-effort`, and `--yolo`. Construction is explicit and covered by fake
Muse tests, including workspace propagation even when the Mac path is absent.
Actual positional parsing and the physical session-reference output envelope
must still be checked against `muse.stdout` / `muse.stderr` from the one canary.
Those files may contain private provider output; do not publish them wholesale.

No session is invented from slot IDs or model text. The default parser accepts
fenced task-result JSON but **does not trust its session_ref**. Resume/message
requires a persisted verified reference and exact goal/task/attempt/dispatch/
slot/workspace binding. The optional `session_ref_format=json-envelope-v1` is a
tested adapter contract, **not a claim that the real CLI emits that format**:
`{"session_ref":"provider-ref","result":{"status":"SUCCESS"}}`.
Do not enable it until the physical transport is confirmed to produce it.
Invalid/unconfirmed output cannot authorize resume. There is no fallback to
an old checkpoint's prose or to a fresh exec after a failed resume.

## Normal wall operation after canary approval

Configure the existing wall's `config.json` with `worker_config` (absolute path)
and `workspace` (physical canonical Mac path). Confirm
`MUSE_CLI.protocol=headless-v1` in worker configuration (or `COURIER_MUSE_CLI`
JSON). CLI flags beyond the observed interface are not generated.

`start 1|4|8|16|32`, `status`, `stop`, `stop --terminate`, and `resume SLOT`
remain supported. `start` never clears STOP. Explicit `resume all` clears only
the STOP latch; it does not reset uncertain ownership or failed task evidence.
Then an explicit `start N` may enable stopped slots. Never begin physical proof
with 4/8/16/32. A target is a ceiling, not permission to spawn that many at once.

Missing/invalid/stressed metrics admit zero new processes, including replacements.
Healthy admission ramps with a 120-second hold and at most one worker per tick.
Workers independently recheck STOP/resources before claim and Muse launch.
STOP and spawn/claim transitions share a kernel lock; work already admitted
before STOP may drain, but no work starts after STOP is committed.

State writes use unique temporary files, file fsync, atomic replacement and
directory fsync. Corruption is not treated as empty state. Slot STARTING is
persisted before spawn; uncertain starts require reconciliation. Recovered PIDs
require matching OS PID/PGID/start identity, not numeric existence alone.
Muse gets an owned process group, bounded output/time, heartbeats during work,
and TERM/KILL cleanup. Unknown/leaked children block further claims. This does
not claim to contain a deliberately detached descendant that escapes its group.

Foreign checkpoints are preserved as quarantine evidence and not fed to new
tasks. Resume on mismatched binding is blocked. New logical tasks use exec.
Results stay RESULT_PENDING in memory until durable RESULT_READY succeeds;
storage failure cannot send success or claim new work. After a process crash
without a durable result, STARTED recovery remains ambiguous/no-blind-replay.

## Targeted verification (no real providers)

```sh
COURIER_API_KEY=synthetic-worker-test COURIER_VERIFIER_API_KEY=synthetic-verifier-test \
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_muse_convergence.py tests/test_muse_supervisor.py \
  tests/test_mac_worker_recovery.py tests/test_mac_worker_contract.py \
  tests/test_integration_contract.py tests/test_server_integration_contract.py
```

Integration fixtures use a temporary localhost server, fake Muse executable,
temporary workspaces/state, and a test-only bootstrap replacing Keychain/config
and resource probes. They clean up only their recorded owned children.

Verified locally on 2026-09-25 with the six-file command above: **94 passed**.
The process-cleanup proof used only a synthetic Python process in its own group.
Real Muse/provider execution and the physical canary were not run.
