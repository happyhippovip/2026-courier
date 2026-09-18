# Cloud + ChatGPT Alignment — 2026-09-18

This document records the architecture points where the morning Cloud review and ChatGPT operating plan agree, plus the specific additions adopted for Courier Symphony Muse.

## Shared conclusion

The highest-value architecture is:

NEWSY / read-only scout
→ MUSE invariant + architecture + packet QA
→ GOOGLE implementation + Windows/runtime
→ T0 → T1 → T2
→ related fixes batched where safe
→ T3 adversarial gate
→ CODEX independent review only when justified
→ T4 at coherent integration boundary
→ close + artifact update

The goal is not raw quota burn.

The goal is:

VERIFIED OUTPUT PER HOUR
+
VERIFIED OUTPUT PER CODEX %
+
ZERO STALE/FALSE LEDGER PROOF.

## Why this split

Discovery is expensive but reusable.

Implementation is comparatively mechanical once a task is prepared.

Independent verification is expensive and should be reserved for places where independence, hard reasoning, concurrency/restart ambiguity, or physical-proof confidence is the true bottleneck.

Therefore:

- MUSE and NEWSY absorb repository archaeology once.
- GOOGLE consumes precise ready-to-implement packets.
- CODEX receives compact review packs rather than open-ended exploration.

## Required task packet

A ready packet contains:

- TASK_ID
- PRIORITY
- CURRENT_HEAD
- OWNER
- BUG
- EVIDENCE
- EXACT_FILE
- EXACT_FUNCTION
- REPRODUCER
- EXPECTED_INVARIANT
- CURRENT_BAD_BEHAVIOR
- TARGETED_TEST_COMMAND
- NEGATIVE_TEST
- AFFECTED_SUITE
- REPLAY_CASE
- RESTART_CASE
- CONCURRENCY_CASE
- PROVIDER_WAIT_CASE
- DEPENDENCIES
- CAN_BATCH_WITH
- READY_TO_IMPLEMENT

If required information is missing, the packet is not ready.

## Test lanes

### T0 — preflight
Syntax, compile/import, schema and isolation sanity.

### T1 — exact regression
Fast targeted loop. Early exit may be used while iterating, but the complete targeted set must pass before closure.

### T2 — affected component
Run the component/dependency suite defined in TEST_MAP.

If T1 passes and T2 fails, treat that as evidence that TEST_MAP impact mapping is incomplete.

### T3 — adversarial truth suite
Keep this small and fast. It should cover the core Courier invariants:

- duplicate-result semantics
- replay/stale evidence
- self-certification
- wrong SHA/runtime
- false CLEAN_IDLE
- false QUEUE_INDEPENDENT
- WAITING_PROVIDER isolation
- restart/resume
- duplicate external effects
- worker identity
- test isolation

### T4 — integration/full
Run only at coherent integration boundaries, before handoff/deploy, or when impact mapping is uncertain.

## Zero-hang policy

- Every test/subprocess gets a bounded lifetime.
- Every spawned child is associated with an owner/test ID.
- Track exact PIDs.
- Cleanup only owned PIDs.
- Never use generic killall for shared process classes.
- Dump diagnostics before timeout cleanup.
- Post-suite target: OWNED_CHILD_PROCESSES=0.

## Parallel test policy

Classify explicitly:

- PARALLEL_SAFE
- PROCESS_ISOLATED
- SERIAL_SHARED_STATE
- PHYSICAL_SERIAL

Do not infer parallel safety from directory location.

Start with low fixed parallelism; never allow test parallelism to starve agents, localhost, or canonical runtime work.

## Tooling decisions

- pytest-timeout: strong immediate candidate.
- pytest-xdist: test first on explicitly parallel-safe suites only.
- pytest-testmon: optional cross-check, not source of truth for side-channel/runtime dependencies.
- pytest-picked: not currently required because packets already provide exact test commands.
- TEST_MAP remains the authoritative routing layer.

## NEWSY prefetch

While Google executes task N, NEWSY should prepare N+1, N+2, N+3 whenever genuine work exists.

NEWSY is read-only.

NEWSY locates and reproduces; MUSE decides ambiguous invariants.

## MUSE broker rule

MUSE routes work as follows:

1. Undefined/ambiguous invariant → MUSE decides.
2. Cross-component architecture/causal reasoning → MUSE.
3. Mechanical prepared implementation → GOOGLE.
4. Read-only tracing/reproduction → NEWSY.
5. Prepared high-risk task requiring independence → CODEX.
6. Not yet ready → discovery/deferred queue.

## GOOGLE fast path

Google should spend most active time implementing, not rediscovering.

Loop:

packet
→ verify repro
→ minimal root-cause fix
→ T0
→ T1 fast
→ T1 full
→ T2
→ self-attack
→ coherent commit
→ next packet

If Google needs broad repo archaeology outside the packet, classify PACKET_INCOMPLETE and return it to NEWSY/MUSE.

## CODEX economy

Codex is a scarce independent-verification resource.

Do not use it for:

- broad grep/search
- routine pytest
- routine file reading
- docs generation
- mechanical edits
- repeated environment setup

Use it for:

- high-value independent review
- producer/verifier independence
- hard concurrency/restart defects
- cross-component ambiguity
- conflicting conclusions between cheaper agents
- final integration
- exact physical-proof verification

### Codex batch review

Batch related fixes when:

- same invariant family,
- combined logical diff remains reviewable,
- no high-risk item loses scrutiny.

A Codex review packet must include:

- CURRENT_HEAD
- COMMITS_UNDER_REVIEW
- INVARIANTS
- DIFF_SCOPE
- REPRODUCERS
- T2_RESULTS
- T3_RESULTS
- KNOWN_ATTACKS
- FILES_TO_READ
- QUESTIONS_TO_ANSWER

Missing packet data → PACKET_INCOMPLETE → NEWSY/MUSE.

## Codex weekly controller

Recompute from actual remaining allowance and time to weekly reset.

Maintain a reserve for final integration/hard verification.

Do not invent work simply to hit a minimum utilization target.

Track:

- Codex % used per day
- Codex % per verified bug/review
- review batch size
- PACKET_INCOMPLETE count
- bounce rate
- discovery tasks offloaded from Codex

## Productive high-volume work

Good high-volume work:

- adversarial matrices
- negative tests
- restart/concurrency/provider-wait matrices
- reproducers
- failure signatures
- source/test maps
- Ledger packets
- Windows exact-SHA preflight
- artifact-pack maintenance
- security/integration attacks

Bad high-volume work:

- repeating unchanged grep
- rereading unchanged files
- repeated full-suite runs
- fake backlog items
- status prose
- using Codex for mechanical work

## Ledger factory

A real Ledger work-bank entry requires evidence, exact file/function, reproduction, invariant, and target test.

Do not pad the queue.

Measure the gap between:

REAL_LEDGER_TASKS_FOUND

and

READY_TO_IMPLEMENT

A growing gap means packet preparation is slower than Google consumption.

## Windows factory

Every Windows packet must state the downstream Ledger invariant/evidence it supports.

Examples:

process identity ↔ exact SHA
→ runtime/freshness evidence

restart/resume test
→ durable checkpoint/resume evidence

two-worker concurrency
→ duplicate-effect / queue-independence evidence

Windows work must not become a disconnected side project.

## Morning architecture delta

Do not redesign daily.

Compare measured metrics against ARCHITECTURE_BASELINE.

- within ±20% → KEEP_ARCHITECTURE
- isolated >20% regression → TUNE_PARAMETER
- Codex bounce >15% for two consecutive days → CHANGE_ROUTING_RULE
- unjustified full-suite growth → CHANGE_TEST_LANE
- >=3 simultaneous major regressions → ARCHITECTURE_REVIEW
- any unexplained hang/orphan process → immediate investigation

## Customer / external actions

Safe reversible prerequisites may be prepared automatically.

Real payment, customer contact, publication, public deployment, pilot onboarding, credential rotation, or other irreversible business action requires explicit authority.

Preparation is never proof the external action happened.

## Permanent rule

PACKET FIRST.
ONE WRITER.
T0 → T1 → T2.
T3 BEFORE CODEX.
CODEX ONLY WHEN INDEPENDENCE/HARD REASONING MATTERS.
T4 ONLY AT BOUNDARIES.
BLOCKED TASK != BLOCKED PROJECT.
LEDGER LAST.
NO FAKE GREEN.
