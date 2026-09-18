# Courier Symphony Muse — AI Engineering Operating System

## Objective

Maximize:

- verified engineering output per hour,
- verified output per Codex percentage,
- reuse of expensive discovery,
- Google implementation throughput,
- truthful Ledger/Guard/Motor progress,
- Windows exact-SHA and physical-acceptance readiness.

Do **not** optimize for raw token burn or pretty green status.

## Architecture

```
NEWSY (read-only prefetch, depth 3)
        ↓
MUSE (invariant, architecture, packet QA)
        ↓
GOOGLE (implementation + Windows/runtime, T0→T1→T2)
        ↓
related fixes grouped when safe
        ↓
T3 adversarial gate
        ↓
CODEX (independent review only when justified)
        ↓
T4 at integration boundary
        ↓
close + artifact update
```

## Task packet contract

A task is ready for implementation only when it contains:

```
TASK_ID=
PRIORITY=
CURRENT_HEAD=
OWNER=

BUG=
EVIDENCE=

EXACT_FILE=
EXACT_FUNCTION=

REPRODUCER=
EXPECTED_INVARIANT=
CURRENT_BAD_BEHAVIOR=

TARGETED_TEST_COMMAND=
NEGATIVE_TEST=
AFFECTED_SUITE=

REPLAY_CASE=
RESTART_CASE=
CONCURRENCY_CASE=
PROVIDER_WAIT_CASE=

DEPENDENCIES=
CAN_BATCH_WITH=
READY_TO_IMPLEMENT=
```

No fake backlog inflation. Half-known items belong in discovery, not the executable queue.

## Test lanes

### T0 — preflight
Run on every edit where relevant:
- syntax,
- compile/import,
- schema sanity,
- test-isolation sanity.

Target: seconds.

### T1 — exact regression
During inner loop, fast fail is allowed (`-x --maxfail=1`). Before task completion, run the full targeted set without early exit.

Target: seconds to about one minute where practical.

### T2 — affected component
Use `TEST_MAP.yaml` to run only affected suites and declared dependencies.

If T1 passes and T2 fails, treat this as evidence that the impact map is incomplete; update the map instead of blindly running everything.

### T3 — adversarial truth suite
Small, fast core suite covering:
- duplicate result semantics,
- replay/stale evidence,
- self-certification,
- wrong SHA/runtime,
- false CLEAN_IDLE,
- false QUEUE_INDEPENDENT,
- WAITING_PROVIDER isolation,
- restart/resume,
- duplicate effects,
- worker identity,
- test isolation.

Keep T3 small enough to remain useful as a gate.

### T4 — broader/full integration
Run only:
- at coherent integration boundaries,
- before handoff,
- before reviewed candidate/deploy,
- when impact mapping is uncertain.

Do not run T4 after every small edit.

## Zero-hang law

- Every test or subprocess has a bounded lifetime.
- Every spawned child belongs to a test/owner ID.
- Track exact PIDs.
- Cleanup kills only owned PIDs.
- No generic `killall python3`, `killall agy`, or equivalent.
- Dump diagnostics before terminating a timed-out child.
- Post-suite target: `OWNED_CHILD_PROCESSES=0`.

## Parallel test classes

- `PARALLEL_SAFE`: no shared state/ports/processes — can run parallel after measurement.
- `PROCESS_ISOLATED`: owns its children and resources — fixed low parallelism only.
- `SERIAL_SHARED_STATE`: shared Courier state/ports/runtime — serial.
- `PHYSICAL_SERIAL`: canonical Windows/physical acceptance — serial and isolated.

Do not infer these classes from directory location; mark them explicitly.

## Tooling decisions

- `pytest-timeout`: strong candidate for immediate adoption, together with explicit subprocess timeouts.
- `pytest-xdist`: test first on explicitly marked parallel-safe suites; start with low fixed worker count.
- `pytest-testmon`: optional cross-check only; do not replace authored TEST_MAP semantics.
- `pytest-picked`: not currently needed if packets already supply exact test commands.

## Google fast path

```
pull ready packet
→ verify reproducer
→ implement minimal root-cause fix
→ T0
→ T1 fast until green
→ T1 full
→ T2
→ self-attack / negative test
→ coherent commit
→ next packet
```

If Google needs broad discovery outside the packet, classify the packet as incomplete and return it for repair instead of silently expanding scope.

## NEWSY prefetch

While Google works task N, NEWSY prepares N+1, N+2, N+3:
- exact file/function,
- reproducer,
- expected invariant input for MUSE,
- target/negative tests,
- dependencies,
- ownership,
- affected suite.

NEWSY does not decide invariants and does not write canonical code.

## MUSE routing

1. Invariant undefined/ambiguous → MUSE decides first.
2. Cross-component/architecture causal reasoning → MUSE handles or packetizes.
3. Fully specified mechanical implementation → GOOGLE.
4. Read-only tracing/reproduction → NEWSY.
5. High-risk prepared independent-review need → CODEX.
6. Not ready → discovery/deferred queue, not Codex.

MUSE should not spend large amounts of time doing routine test execution that Google can perform.

## Codex usage philosophy

Codex is a scarce independent verifier, not a broad exploration worker.

Never use Codex primarily for:
- broad repo search,
- routine file reading,
- routine pytest,
- documentation generation,
- mechanical fixes,
- repeated environment setup.

Prefer Codex for:
- producer/verifier independence,
- hard concurrency/restart defects,
- cross-component ambiguity,
- contradictory conclusions from cheaper agents,
- final integration,
- physical-proof verification.

## Productive high-volume work

Good:
- adversarial matrices,
- negative tests,
- reproducible task packets,
- failure signatures,
- source/test maps,
- Windows preflight,
- restart/provider/concurrency matrices,
- security review,
- artifact updates.

Bad:
- repeating the same grep,
- rereading unchanged giant files,
- rerunning unchanged full suites,
- status prose,
- fake queue items,
- using Codex for mechanical work.

## Morning architecture rule

Do not redesign the architecture every morning.

Compare yesterday's measured values against `ARCHITECTURE_BASELINE.md`.

- within ±20% → keep architecture,
- isolated >20% regression → tune parameter,
- Codex bounce >15% for two consecutive days → change routing,
- unjustified increase in full-suite runs → change test lane,
- >=3 major simultaneous regressions → architecture review,
- hangs/orphans >0 → immediate investigation.

## Human / external gates

Preparation may be automated; real irreversible/business actions remain gated:
- payment,
- customer contact,
- publication,
- public deployment,
- pilot onboarding,
- credential rotation.

Preparing a payload/document/checklist never counts as proof the real external action happened.
