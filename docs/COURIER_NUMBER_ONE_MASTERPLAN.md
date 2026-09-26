# COURIER NUMBER ONE MASTERPLAN

Status: Strategic operating plan
Date: 2026-09-26
Rule #1: CONTINUE BY DEFAULT

## Mission

Build Courier into the most trustworthy, durable and provider-independent autonomous work control plane we can prove.

The target is not "more agent windows". The target is:

`ONE HUMAN START -> VERIFIED CONTINUATION -> HUMAN ONLY FOR REAL GATES`

Courier should become more valuable than any single coding model or agent because it owns the durable control plane around models:

`GOAL -> CONTRACT -> QUEUE -> CLAIM -> ADMIT -> EXECUTE -> RESULT -> VERIFY -> LEARN -> NEXT`

## The strategic thesis

Models will keep changing. The durable asset is the system that knows:

- what the human actually authorized
- what task is next
- who owns it
- what already happened
- what is safe to retry
- what result is real
- what evidence proves it
- what can continue without the human
- what must stop for a real gate

Courier wins by being the trustworthy operating layer across Muse, Codex, Google/Antigravity, Opus and future providers.

## Rule Zero: Finish before expansion

Never confuse visible scale with product proof.

Order:
1. Trusted ledger
2. Reliable motor
3. Physical zero-human A->B
4. Restart/recovery
5. Resource-safe multi-worker scale
6. Multi-host
7. Vacation mode
8. Customer pilot
9. Product shell
10. Repeatable distribution

No later gate can substitute for an earlier gate.

## Moat 1 — Verified continuity

Courier must prove:
- result survives process death
- RESULT_READY is redelivered, not recomputed
- ambiguous STARTED is never blind-replayed
- next task is dispatched without human relay
- writer scope remains exclusive
- restart resumes the same identity chain
- provider rate limit creates a durable pause, not lost work
- idle worker capacity can be replenished automatically

Primary metric:
`HUMAN_RELAYS_PER_GOAL -> 0`

## Moat 2 — Provider independence

No provider may become the system of record.

Every worker adapter must map into the same task contract:
- goal_id
- task_id
- attempt_id
- dispatch_id
- worker_execution_id
- host_id
- provider
- model/tier
- write_scope
- heavy flag
- dependencies
- expected evidence
- terminal result

Providers are replaceable workers. Courier remains authoritative.

## Moat 3 — Evidence, not self-report

A model saying "done" is not completion.

Verification preference:
1. deterministic check
2. reproducible test
3. independent reviewer
4. physical end-to-end proof

Every major product claim must have a candidate SHA/config/runtime binding and evidence.

No evidence -> no PASS.

## Moat 4 — Compounding organizational memory

Every completed task should improve future work.

Persist:
- discovered architecture
- failure modes
- accepted patterns
- rejected approaches
- test gaps
- provider quirks
- cost/runtime observations
- recovery lessons

Use this memory to reduce future tool calls, context loading and duplicate investigation.

The target is not just task completion. It is declining cost per verified useful outcome.

## Moat 5 — Resource-aware autonomy

64 logical workers must not mean 64 heavy processes.

Resource governor decides admission.

Mac initial:
- max heavy = 1

Windows initial:
- max heavy = 2

Scale only with measured evidence.

Large backlog is cheap.
Idle logical slots are cheap.
Heavy execution is scarce and deliberately admitted.

## Moat 6 — One authority

Exactly one component owns:
- queue state
- task claim
- retry/reconciliation
- next-task dispatch

No second scheduler.
No competing wall.
No hidden provider-specific scheduler that can create duplicate authority.

Wall/dashboard is projection, not authority.

## Moat 7 — Vacation Mode

Acceptance:

1. Human starts Courier once.
2. Task A is dispatched.
3. Worker executes.
4. Result A is durably persisted.
5. Courier verifies A.
6. Task B is dispatched automatically.
7. This repeats across worker/session boundaries.
8. Restart does not duplicate effects.
9. Rate limits create durable parked states.
10. When capacity returns, eligible work resumes.
11. Human is contacted only for real gates.

Target:
`CONTINUE_BY_DEFAULT`

## Competitive benchmark

Never claim superiority from vibes or terminal count.

Benchmark Courier against single-agent baselines on the same repo/tasks.

Measure:
- verified tasks/hour
- human relays/task
- duplicate execution count
- lost result count
- restart recovery success
- time from RESULT to NEXT
- cost per verified task
- tool calls per verified task
- percent of tasks with deterministic evidence
- percent of failures safely recovered
- idle control-plane overhead
- long-run completion rate

A win must be reproducible and evidence-backed.

## Einstein-style principle: simplify to invariants

Do not copy a historical person or claim what they would literally do.

Apply the useful principle:
reduce the problem until only the invariant remains.

For Courier:
"After every state transition, can we prove what happened and what is allowed next?"

If not, architecture is still too complicated.

## Feynman-style principle: explain every subsystem simply

For every subsystem, require a five-sentence explanation understandable without internal jargon.

If the team cannot explain:
- who owns the state
- what the input is
- what the output is
- what can fail
- how it recovers

then simplify it.

## Shannon-style principle: preserve the signal

The valuable signal is:
- intent
- identity
- evidence
- state transition

Everything else is noise until proven useful.

Reduce prompt size and duplicated context by moving durable facts into structured state.

## Deming-style principle: improve the system, not heroic workers

Do not depend on one great 42-minute session.

Design the system so an average worker can:
- claim correctly
- execute within scope
- return durable evidence
- fail safely
- hand off to the next worker

The product is the process.

## Bezos-style principle: work backward from the customer

Customer promise:

"Start the goal once. Come back later. Courier can show exactly what happened, what was verified, what remains, and why it stopped if it stopped."

Build backward from that statement.

## Strategic independence

The company must not require acquisition to succeed.

Design for:
- profitable paid pilots
- low infrastructure cost
- provider competition
- local-first capability
- exportable customer evidence
- portable task contracts
- no single-platform dependency
- customer-owned data paths where possible

Acquisition is optional.
Sustainable standalone value is the target.

## 90-day path

### Phase A — Truth
Finish Trusted Ledger and bind claims to exact runtime evidence.

### Phase B — Motor
Physical Task A -> Result -> Verify -> Task B with HUMAN_RELAYS=0.

### Phase C — Recovery
Prove process crash, supervisor restart, provider limit and machine reboot paths.

### Phase D — Scale
1 -> 4 -> 8 -> 16 safely.
Then 30/45 logical slots with bounded active work.

### Phase E — Vacation Mode
Multi-hour and overnight bounded soaks.
Measure every transition.

### Phase F — Pilot
Find one real customer workflow where continuation is worth money.
Do not sell "45 agents".
Sell "work continues safely and comes back with evidence."

### Phase G — Product
One-command install.
One goal entry point.
One status surface.
One evidence trail.
One safe stop.
One exportable audit.

## Kill list

Do not spend scarce time on:
- terminal-window theater without evidence
- duplicate schedulers
- provider-specific permanent architecture
- branch multiplication
- UI before motor proof
- broad stress tests before canaries
- fake benchmark numbers
- self-reported success without evidence
- adding models merely because they are available
- cloud spend for work that can run locally

## Today's highest-value sequence

1. Preserve running Muse long sessions.
2. Codex High reviews physical runtime/crash/duplicate path.
3. Opus High performs convergence/integration review.
4. Existing single writer receives one minimal delta.
5. Physical Canary: Task A -> Result -> Task B automatically.
6. Scale to 4.
7. Record real metrics.
8. Only then scale to 8/16.
9. Run 60-120+ minute soak.
10. Produce demo from real telemetry.

## Number-one standard

Courier is not #1 because we say so.

Courier earns #1 by repeatedly demonstrating:

- less human relay
- more verified continuity
- fewer duplicated effects
- fewer lost results
- safer restart
- lower cost per verified outcome
- provider independence
- better long-run reliability

The benchmark is the judge.
