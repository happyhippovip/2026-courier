# Courier Symphony — Growth Goals & Idea Ledger — 2026-09-26

Status: ACTIVE IDEA/GOAL LEDGER  
Authority: records product/operations goals; does **not** override the current canonical proof path or final-writer scope.

## North Star

Courier should let a person say what they want once, then reliably continue useful work across providers, machines, sessions, restarts and long unattended rounds — while remaining truthful about what is actually running, verified, blocked, guarded or idle.

## Current proof path stays first

Before broad implementation expansion:

1. FINAL_CANONICAL_CANDIDATE
2. REAL_TARGETED_TESTS
3. independent code-grounded review
4. RUN_1: A -> verify/reconcile -> B, zero human relay
5. RUN_2: restart/no-A-replay
6. minimum honest dual-surface UI

New ideas below are captured now so they are not lost, but they must not weaken those gates.

## G1 — Exact Wall Size 1..64

The user must be able to choose any exact logical wall size from 1 through 64.

Examples:
- 1 = tiny local setup
- 2 / 3 = simple free-package starter sizes
- 6 = modest laptop
- 10 = preferred smooth Windows/Mac target when host conditions fit
- 16 = larger wall only when it remains smooth
- 30 = large Muse wall
- 37 = previously requested larger surface
- 64 = current maximum requested product surface

Important:
requested_slots != heavy_processes

A slot is a logical lease/capacity unit. Runtime admission may reduce active work when host, provider, cost, dependency or safety guards require it.

Truthful surface:
- REQUESTED
- ADMITTED
- ACTIVE
- WAITING
- GUARDED
- RESERVED_INTERACTIVE
- IDLE
- DONE

Never fake "64 active" merely because 64 were requested.

## G2 — Reserve Interactive Slots

Users may reserve some capacity for interactive work.

Example:
- WALL_SIZE=10
- RESERVED_INTERACTIVE=2
- AUTONOMOUS_TARGET=8

Reserve count must be configurable. The system should not consume reserved interactive slots for unattended work.

## G3 — Long Sleep Rounds

Courier should support bounded unattended rounds such as:
- 30 min
- 1 h
- 2 h
- 3 h
- 4 h
- 5 h
- 6 h
- 8 h
- 10 h

A long round is productive continuation, not busywork.

A smooth 10-slot wall for 10 hours is preferred over a laggy 16-slot wall that wastes CPU/RAM/API or increases error risk.

Every round remains bounded by:
- wall-clock budget
- provider/session availability
- host resource guard
- cost budget
- finite retries/failures
- dependency-safe READY work
- repeated-state/no-progress detection
- writer ownership
- context-hygiene checkpoints

When no safe authorized work remains: persist IDLE/DONE/BLOCKED and stop.

## G4 — One Universal Prompt Across Mac / Windows / Google CLI / Muse

The operator should be able to paste substantially the same mission into:
- 🍎 Mac
- 🪟 Windows
- 🟨 Google / Antigravity CLI
- 🟣 Muse

The prompt self-detects host/provider, loads canonical coordination truth, chooses one unowned logical slot and continues within its assigned authority.

Default autonomous mode is READ_ONLY/REPORT_ONLY.

Source mutation requires explicit durable writer authority.

## G5 — Ledger-Driven Wall

The final wall must be driven by the canonical Trusted Ledger, not by counting terminal windows.

Every work unit binds to:

GOAL
-> CONTRACT
-> TASK
-> ATTEMPT
-> CLAIM/LEASE
-> DISPATCH/EXECUTION
-> RESULT
-> EVIDENCE
-> VERIFY
-> RECONCILE
-> NEXT

Restart must preserve identity and prevent blind replay.

The Ledger decides what work is already done, owned, stale, blocked, contradictory or READY.

## G6 — Featherlight Slots

Idle logical slots should consume near-zero CPU/RAM/API.

Prefer:

event/result-driven dispatch
-> work
-> DurableResult
-> verify/reconcile
-> release/reuse slot

Avoid:
- resident AI polling
- tight loops
- repeated unchanged scans
- repeated unchanged tests
- duplicate reviewers
- idle terminals whose only job is waiting

The wall should feel large without requiring the host to carry 64 heavy resident processes.

## G7 — Bigger Work Packages

Agents should receive meaningful work packages, not tiny prompt fragments.

Task sizes:
- SMALL: 10–30 min
- MEDIUM: 30–90 min
- LARGE: 2–4 h
- SLEEP: 3–10 h bounded round

Large work must still have a clear scope, evidence target, stop condition and ownership boundary.

Examples of LARGE read-only packages:
1. full 12-case final evidence matrix
2. duplicate/replay + lost-ACK audit
3. restart durability + crash-window map
4. trusted artifact/hash chain
5. auto-B eligibility/dispatch proof
6. claim/lease concurrency audit
7. cross-platform portability audit
8. resource/thermal/process-safety audit
9. stale-truth/branch-evidence reconciliation
10. Ledger gaps from Goal through Reconcile

## G8 — Growing Crew / Role Library

Courier should grow a reusable team of specialist roles.

Initial families:

### Truth & Ledger
- Ledger Integrity
- Result Identity
- Duplicate/Replay
- Stale Truth
- Provenance

### Motor
- READY/Eligibility
- Auto-Next
- Dispatch
- Lease/Claim
- Retry/Backoff

### Verification
- Artifact Truth
- Contract Verification
- Failure Semantics
- Proof Cards

### Recovery
- Restart Durability
- Crash Windows
- Orphan Recovery
- Lost ACK

### Runtime / Safety
- Thermal/Resource Guard
- Process Ownership
- Cost/Quota Guard
- Portability

### Product
- Grandma Test
- Dual-Surface Truth
- Pilot Readiness
- Onboarding Friction
- Accessibility/Icon Truth

Crew growth must be de-duplicated: add a role only when it closes a distinct recurring evidence need.

## G9 — Continuous Idea Engine

A small minority of capacity may continuously improve the product idea set.

Rules:
- never steal critical-path capacity
- never create tasks just to stay busy
- deduplicate against this ledger
- every proposal must state the concrete user benefit
- classify NOW / NEXT / LATER / NON-GOAL
- distinguish idea from proven need
- prefer improvements that reduce relay, cost, risk or cognitive load

Suggested allocation:
- 70–85% critical-path/evidence work
- 10–20% recovery/resource/product-readiness
- 5–10% idea exploration

## G10 — Friendly Visual Language

Courier should use small visual cues alongside truthful text.

Examples:
🎯 Goal
📜 Ledger
🧠 Plan
🚀 Ready/Dispatch
👀 Read-only
✍️ Writer
🧪 Verify
✅ Verified/Done
🟡 Waiting
🛡 Guarded
💤 Idle
🔁 Restart/Recovery
🔥 Thermal pressure
💸 Budget/Quota
🧩 Dependency
🍎 Mac
🪟 Windows
🟨 Google CLI
🟣 Muse
🌍 Product world / larger mission

Icons never replace state text. Decorative visuals must not imply success that is not proven.

## G11 — Result Harvester / Human Is Not the Message Bus

The operator should not manually collect 10–30 agent results.

Courier should:
1. ingest/checkpoint returned reports
2. classify PROVEN / OPEN / BLOCKED / STALE / CONTRADICTED
3. deduplicate findings
4. attach evidence to Ledger identities
5. compute the next dependency-safe READY work
6. refill freed logical slots automatically
7. surface only decisions that really need the human

## G12 — Cost / Quota-Aware Routing

Scheduling should understand:
- subscription quota
- API spend
- model/provider cost
- remaining time until reset
- proof value per cost
- proof value per wall-clock minute

Prefer free/cheaper read-only scouting for broad work.

Use scarce/high-cost models only when they materially change a decision, close a blocker or independently validate critical proof.

## G13 — Cross-Platform Team

Mac and Windows are peers, not remote-control targets for one another.

Each host:
- has independent resource guard
- has its own logical slots
- preserves writer ownership
- reports durable evidence
- can continue useful independent work

The Ledger reconciles them into one truthful product state.

## G14 — Larger Product World, Real Work First

Courier may eventually feel like a larger living work world:
- start area
- clear paths
- specialist roles
- visible progression
- teams/projects
- tools/capacity
- challenges
- more useful possibilities over time

But it remains real work, not fake gamification.

Progress should derive from verified useful work, not clicks, login streaks or artificial activity.

This idea is LATER until core proof is complete.

## G15 — Context Hygiene / Clear-by-Default

Active AI context is a bounded resource.

When old information no longer affects the next decision:

CHECKPOINT
-> CLEAR
-> LOAD MINIMAL CURRENT TRUTH
-> CONTINUE

Every agent/chat/provider handoff should be featherlight.

Do not drag obsolete logs/history into a new phase.

See:
ops/ai/CONTEXT_HYGIENE_AND_HANDOFF_POLICY_2026-09-26.md

## G16 — V1 Automatic Updates + Daily Safety Review

V1 should eventually support:

- daily update checks;
- fast signed/verified updates at application/host boot;
- rollback to last known-good version;
- small/delta/component patches where safe;
- daily bounded safety-review agents;
- cryptographic agility and post-quantum readiness tracking.

Do not claim "quantum secure" without a proven concrete profile.

See:
docs/V1_CAPACITY_UPDATES_AND_CRYPTO_READINESS_PLAN.md

## G17 — Beginner Wall + Subscription-First UX

Normal customers should not need API keys.

Courier should expose clean beginner wall presets such as 1 / 3 / 5 / 6 / 9 / 10 / 12 / 16, while retaining exact logical wall selection in advanced mode.

Provider subscriptions should be usable as the normal path; API/PAYG belongs in an optional developer/advanced surface.

See:
docs/COURIER_V1_BEGINNER_WALL_AND_COMMUNITY_VISION_2026-09-27.md

## G18 — Focus / Background Mode

Users should be able to hide the operational wall and see only the project world/background, chat, people/community and a lightweight truthful status.

The control plane stays one click away.

## G19 — Community + Verified Contribution

Longer-term community should center on useful verified contribution, teams, goals and reputation rather than fake engagement.

Any contribution-linked rewards are exploratory.

Equity, ownership, investment return or revenue-share promises require a separate legal/compliance design before implementation or marketing.

## G20 — Cheapest-Suitable Model Routing

Courier should route broad routine work to cheaper/faster models and reserve premium models for convergence, difficult code-grounded review, contradiction resolution and release-readiness judgment.

Exact provider plans/prices are configuration and must not be hard-coded as permanent product truth.

## Design invariant

Bigger must mean:

**more verified useful work with less human relay**

—not more windows, more agents, more noise or more CPU merely for appearance.
