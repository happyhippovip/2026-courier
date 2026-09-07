# IDEA FOUNDRY — Gedankenlager → Opportunity → Product → Evidence → Value

Status: Product/operating hypothesis. Evidence-first; no invented revenue claims.

## Purpose
The human should be able to drop raw thoughts, fragments, chats, problems and ambitions into one Gedankenlager. The system does not merely store them. A persistent AI team turns them into organized, deduplicated, connected, challenged and progressively executable opportunities.

North Star:
`RAW THOUGHT → CAPTURE → CLASSIFY → CONNECT → SYNTHESIZE → CHALLENGE → OPPORTUNITY → PRODUCT HYPOTHESIS → EXPERIMENT → COURIER GOAL → BUILD → VERIFY → FOUNDER REVIEW → OUTCOME → ECONOMIC EVIDENCE → LEARN → NEXT BEST ACTION`

The user supplies ideas and genuine human decisions. The system supplies organization, research, synthesis, planning, execution, verification and learning.

## The Gedankenlager
Never destroy the raw original. Every thought receives immutable provenance and can later be reinterpreted.

Minimum record:
- thought_id
- raw_text
- created_at
- source
- provenance
- classification
- themes/tags
- related_thought_ids
- contradictions
- assumptions
- open_questions
- confidence
- status

Classifications include FACT, USER_INPUT, IDEA, PROBLEM, DESIRE, ASSUMPTION, INFERENCE, OPEN_QUESTION, DECISION, ACTION_ITEM, RISK and OPPORTUNITY_SIGNAL.

## Idea Foundry Team
These are logical roles/capabilities, not necessarily separate expensive model calls.

### 1. INTAKE KEEPER
Captures everything losslessly, timestamps it, preserves source/provenance, and never silently rewrites the original.

### 2. LIBRARIAN / SORTER
Clusters thoughts by problem, customer, product, technology, urgency and evidence. Deduplicates semantic repeats without deleting originals. Detects stale and superseded interpretations.

### 3. CONNECTOR
Finds useful relationships between old and new thoughts: same underlying problem, complementary capabilities, contradictions, dependencies, reusable assets and previously abandoned ideas that become relevant again.

### 4. IDEA SYNTHESIZER
Combines compatible fragments into explicit Idea Candidates. It must show which source thoughts produced the candidate and distinguish source evidence from inference.

### 5. SKEPTIC / RED TEAM
Attempts to kill weak ideas early. Looks for fake problems, unclear buyer, expensive support, regulatory/security burden, commodity features, unverifiable value, hidden human labor and unnecessary technical scope.

### 6. OPPORTUNITY ANALYST
Scores surviving candidates by evidence-weighted, risk-adjusted leverage: problem strength, buyer access, real-use proximity, time-to-value, time-to-revenue, willingness-to-pay evidence, retention potential, differentiation, build effort, provider/ops/support cost, security/compliance, reversibility and confidence. UNKNOWN remains UNKNOWN.

### 7. PRODUCT ARCHITECT
Converts a promising opportunity into the smallest testable product/concierge slice. Reuses existing components before proposing new systems. Defines outcome, acceptance criteria, failure criteria and what explicitly must NOT be built yet.

### 8. EXPERIMENT DESIGNER
Chooses the cheapest experiment that can destroy or strengthen the important assumption. Prefers synthetic/adversarial tests first, then controlled human validation when a Human Gate permits it.

### 9. BUILDER ROUTER
Does not become a second orchestrator. It hands an approved high-level Goal to Courier. Courier remains the only canonical execution/orchestration engine and routes LOCAL_CHEAP → PRIMARY_BUILDER → EXPENSIVE_SPECIALIST.

### 10. VERIFIER
Separates EXECUTED, COMPLETED, VERIFIED, USEFUL and GOAL_SATISFIED. Hashes and passing tests are technical evidence, not automatically customer value.

### 11. VALUE ACCOUNTANT
Tracks only measured or explicitly founder-reported evidence: time-to-useful-outcome, revisions, manual work, repeated use, export/use, provider cost, explicit WTP/pilot signals. Never fabricates savings, revenue, conversion or margins.

### 12. PORTFOLIO / CAPITAL ALLOCATOR
Continuously asks which candidate/job has the highest expected economic/product leverage per constrained hour/provider-euro. It can reprioritize and kill work, but cannot purchase capacity. Autonomous spend limit remains EUR 0.

## Candidate Lifecycle
`RAW → ORGANIZED → CONNECTED → CANDIDATE → CHALLENGED → SCORED → EXPERIMENT_READY → COURIER_GOAL → BUILDING → VERIFIED → FOUNDER_REVIEW → VALIDATING → EVIDENCED → SCALE / ITERATE / PARK / KILL`

Every transition requires evidence appropriate to the transition. No status inflation.

## Combination Rules
The system may combine thoughts when they share a credible problem/outcome or create a stronger experiment together. It must not create Frankenstein products merely because keywords overlap.

Every synthesized candidate records:
- source_thought_ids
- synthesis_reason
- inferred_connections
- contradictions
- unresolved_questions
- expected user outcome
- cheapest falsification test

The raw thoughts remain intact.

## Repair / Healing Loop
The Foundry continuously looks for broken candidates:
- missing provenance
- contradictory requirements
- stale assumptions
- unverifiable acceptance criteria
- duplicated work
- result disconnected from original Goal
- founder revision not propagated
- evidence incorrectly promoted to value

It repairs metadata/specification safely. Product/code changes go through Courier and normal verification rather than silent mutation.

## Developer / Specialist Hiring
"Hiring" means allocating logical agent roles/capabilities, not purchasing subscriptions or creating paid accounts autonomously.

Courier chooses workers by information gain and cost:
- LOCAL_CHEAP: deterministic extraction, clustering, lint/test/evidence checks
- PRIMARY_BUILDER: normal implementation
- CODEX/EXPENSIVE_SPECIALIST: architecture, difficult root cause, adversarial review, critical verification
- HUMAN: expertise, auth, legal/safety/financial approvals and other genuine gates

New specialist roles are created only when a repeated measurable bottleneck exists. Avoid an army of agents that only talks to itself.

## Continuous Discovery / Daily Improvement
At least once per daily improvement cycle, inspect new/changed thoughts and evidence and ask:
1. Is there a newly visible valuable problem?
2. Can two or more fragments form a stronger candidate?
3. Did new evidence invalidate an old candidate?
4. Is a parked idea now cheap/testable because new infrastructure exists?
5. Which active work should be killed or deferred?
6. Which missing evidence would change the biggest decision?
7. What is the highest-value conflict-free next action?

The system learns from outcomes and updates prioritization heuristics. Real evidence overrides old scores.

## No-Idle / Watcher Behavior
Every device Value Commander may inspect the Foundry when direct work is exhausted. It selects conflict-free work such as sorting, connection discovery, red-team analysis, acceptance-test design, stale-assumption audit, validation design or evidence reconciliation. Single-writer rules still apply.

No reflexive STANDBY. Only `NO_HIGH_VALUE_WORK_FOUND` after checking active P0/P1 gaps, new thoughts, broken evidence chains, economic assumptions and candidate portfolio.

## Current Product Fast Path
The current leading candidate remains Founder Concierge / AI Co-Founder-PM until real evidence changes the ranking. Before broad expansion close the current validation-critical chain:
1. DossierGoalMissionLink
2. VerifiedFounderReviewGate
3. PilotEvidenceRecord
Then run controlled Founder validation rather than building giant SaaS scope.

The Foundry may discover stronger opportunities in parallel, but it must not derail the primary product on weak evidence.

## Economic Flywheel
`MORE RAW IDEAS → BETTER ORGANIZATION → BETTER CONNECTIONS → CHEAPER FALSIFICATION → FEWER BAD BUILDS → MORE VERIFIED OUTCOMES → BETTER ECONOMIC EVIDENCE → BETTER PRIORITIZATION → MORE VALUE PER UNIT OF COMPUTE/HUMAN TIME`

This is the intended "money machine": not automatic money creation, but an evidence-driven system that converts idea flow into increasingly better bets while aggressively reducing waste.

## Hard Gates
No autonomous customer outreach, publication, production deployment, purchase/subscription/upgrade/overage, real trading/funds/wallet signing, account rotation or quota evasion. universuX is protected and must never be touched.

## Success Metrics
Initially measure:
- raw thoughts captured with provenance
- useful connections accepted/reused
- candidates generated vs killed/parked
- time from thought to testable candidate
- percentage of builds tied to explicit evidence gaps
- rework avoided
- founder review outcomes
- repeated real use
- measured provider cost
- explicit WTP/pilot evidence when humans authorize validation

Do not optimize vanity counts such as number of agents, ideas, tasks or generated dossiers.
