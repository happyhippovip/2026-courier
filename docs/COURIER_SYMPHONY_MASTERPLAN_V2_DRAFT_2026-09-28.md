# COURIER SYMPHONY — MASTERPLAN V2 DRAFT

Status: STRATEGIC DRAFT; DOES NOT OVERRIDE CURRENT TECHNICAL GATES
Date: 2026-09-28
Rule: Improve speed-to-cash, speed-to-product, and strategic upside without skipping proof.

## 1. One-sentence company thesis

Courier is the **verified autonomy control plane** for work performed by autonomous digital and, later, physical workers.

Short-term customer promise stays simple:

> Courier bringt dich am nächsten Tag genau dort weiter, wo du aufgehört hast.

Long-term category thesis:

> Every autonomous worker needs a durable contract, an execution identity, evidence, verification, recovery, and a safe next action.

Courier makes autonomous work behave like a trustworthy transaction instead of an opaque chat session.

## 2. What does NOT change

The engineering critical path remains:

CANDIDATE STATE RECONCILIATION
-> exact durable candidate
-> smallest required writer pass
-> changed-byte convergence
-> exact Mac binding
-> physical RUN_1
-> physical RUN_2
-> CORE FREEZE
-> minimum real pilot
-> Product Shell only after positive pilot

No UI, robotics demo, fundraising narrative, marketing page, extra agent swarm, or new feature may replace an earlier proof gate.

## 3. Three-track company system

### TRACK A — CASH NOW

Purpose: collect real money before a polished product exists, without making false SaaS claims.

#### A0 — Paid Continuity Audit

Offer:
**Courier Continuity Audit**

Experimental price:
EUR 149 one-time.

Customer receives:
- 60–90 minute workflow interview;
- current handoff/context-loss map;
- manual-relay count;
- failure/restart map;
- one recommended Goal Contract;
- one-page "what Courier would automate" plan.

This is a consulting/design deliverable, not a claim that Courier is production ready.

Commercial rule:
If customer upgrades to the Founding Pilot within 14 days, the EUR 149 may be credited against the pilot price.

Purpose:
- fastest possible first revenue;
- qualify real pain;
- collect workflow language;
- create a natural conversion into the product pilot.

#### A1 — Founding Pilot

Keep the existing low-friction offer:

EUR 390 one-time
7 days
first three paid pilots
one real AI-heavy workflow

Sell:
- setup;
- workflow mapping;
- one bounded real workflow;
- evidence-based run;
- operator support;
- end-of-pilot report.

Do not sell:
- production-ready SaaS;
- guaranteed savings;
- full autonomy before gates prove it.

#### A2 — Managed Team Pilot

Unlock only after at least one positive Founding Pilot.

Experimental range:
EUR 990–2,500

Scope:
- team workflow;
- higher-touch onboarding;
- two or more handoff boundaries;
- measured intervention/support cost;
- explicit renewal decision.

No commitment to this pricing until real customers validate it.

#### Revenue metrics

Track:
- CASH_COLLECTED;
- AUDIT_TO_PILOT_CONVERSION;
- DAYS_TO_FIRST_PAYMENT;
- SETUP_MINUTES;
- SUPPORT_MINUTES;
- HUMAN_INTERVENTIONS_PER_GOAL;
- NEXT_DAY_RETURN;
- CUSTOMER_WOULD_PAY_AGAIN.

### TRACK B — PRODUCT FAST

Purpose: get to a real product without waiting for a polished application.

#### B0 — Proof Core

Finish current gates exactly as already defined.

#### B1 — Pilot Product, not Product Shell

For the first pilots the minimum customer-visible product is:

Goal
-> Arbeitet
-> Braucht dich
-> Fertig
-> Proof Card
-> next action

Manual onboarding is allowed.
A polished dashboard is not required.

#### B2 — Product Shell

Unlock only after positive pilot evidence.

The first shell should expose the proven behavior, not internal architecture.

Minimum:
- Connect;
- create/confirm Goal Contract;
- status;
- human gate;
- result/proof;
- resume.

No marketplace, enterprise admin, giant dashboard, billing platform, or speculative connector expansion.

#### Product velocity metrics

Track:
- TIME_TO_FIRST_PHYSICAL_PROOF;
- TIME_TO_FIRST_PAID_PILOT;
- TIME_TO_FIRST_REPEAT_USE;
- SETUP_MINUTES_PER_PILOT;
- HIPG;
- RSR;
- NDR.

Optimize these, not feature count.

### TRACK C — STRATEGIC ROBOTICS BEACON

Purpose: make Courier strategically interesting to humanoid/physical-AI builders without turning Courier into a robot-control project.

#### Positioning

Courier should NOT compete with:
- robot motion control;
- VLA foundation models;
- simulation;
- teleoperation;
- robot hardware;
- vendor-specific fleet management.

Courier sits ABOVE those systems as a vendor-neutral accountability and continuity layer.

#### The core robotics idea

A physical robot task becomes a **Verified Work Transaction**:

Goal Contract
-> authorized physical task
-> worker/robot identity
-> policy/runtime identity
-> execution
-> physical effect
-> evidence
-> independent verification
-> reconcile
-> next safe action
-> recovery if interrupted

This is the same Courier primitive already needed for digital agents.

#### Future Physical Proof Card

Later physical adapters can bind:
- goal/task identity;
- robot / embodiment identity;
- policy/model version;
- software/runtime fingerprint;
- hardware/firmware fingerprint;
- environment/site fingerprint;
- safety envelope;
- execution timestamps;
- result/effect witness;
- human intervention;
- emergency stop / takeover event;
- verifier;
- rollback / last-known-good state.

These are LATER design fields. They are not permission to expand the current core implementation.

#### Robotics attention plan

NOW, non-code only:
1. write a short public architecture note: "Verified Autonomy for Digital and Physical Workers";
2. define the vendor-neutral Verified Work Transaction;
3. make one diagram showing Courier above model/robot stacks;
4. maintain a list of robotics integration targets.

AFTER CORE FREEZE + positive pilot:
5. build exactly one reference adapter, preferably against a widely accessible simulation/reference ecosystem;
6. demonstrate interruption/recovery + Proof Card on one physical-AI task;
7. publish the evidence, not hype.

Only after that decide whether robotics deserves a product line.

## 4. Unique category

Persistent agents alone are becoming a commodity.

Courier's category is not:
- "another agent";
- "another coding bot";
- "another robot brain";
- "another workflow builder".

Courier's category is:

**Verified Autonomy Infrastructure**

The fundamental object is a **Verified Work Transaction**.

A Verified Work Transaction has:

CONTRACT
IDENTITY
EXECUTION
RESULT
EVIDENCE
VERIFICATION
RECONCILIATION
NEXT_ACTION
RECOVERY

This gives Courier one architecture that can serve:
- coding agents;
- research agents;
- operations agents;
- support agents;
- industrial automation;
- later, physical robots.

## 5. The large-company thesis

Do not claim a trillion-dollar valuation.

The credible venture-scale thesis is:

If autonomous labor becomes a major part of the economy, organizations will need a neutral layer that can answer:

- What was this worker allowed to do?
- What actually happened?
- Which model/robot/runtime did it?
- What evidence proves the result?
- Was it independently verified?
- What happens after a crash?
- Can stale work replay?
- When must a human intervene?
- Which exact version is safe to resume?

If Courier becomes that layer across digital and physical workers, the addressable category could be very large.

The plan must earn this thesis one proof boundary at a time.

## 6. Moat

Potential moat is not model intelligence.

Moat candidates:

1. **Proof graph**
   Durable cross-worker history of contracts, executions, evidence, verification, and recovery.

2. **Recovery semantics**
   Replay-safe restart and deterministic continuation across providers and machines.

3. **Provider neutrality**
   Replace models/workers without losing the work truth.

4. **Autonomy Grades**
   Evidence-bound description of what a system can actually do without human relay.

5. **Physical + digital common contract**
   Same work transaction abstraction across software agents and later embodied workers.

6. **Evidence network effects**
   Reusable verified workflow patterns and capability packs without pooling private customer data.

## 7. Go-to-market order

First customers:
AI-heavy founders, agencies, small technical teams, and service businesses with obvious context loss / copy-paste / handoff pain.

Why first:
- short sales cycle;
- easy access;
- high pain now;
- workflows can be piloted without hardware;
- evidence arrives quickly.

Robotics teams are strategic lighthouse prospects, not the first revenue dependency.

After digital proof:
- robotics software teams;
- simulation teams;
- system integrators;
- fleet operators;
- humanoid developers.

## 8. Messaging by audience

### Paying small customer

"Courier keeps your AI-heavy work moving and gives you proof of what happened."

### Technical buyer

"Courier is a restart-safe, evidence-bound control plane for autonomous work."

### Robotics / physical-AI builder

"Courier adds durable task contracts, execution provenance, verification, human gates and recovery above your robot brain and fleet stack."

### Investor / strategic partner

"Courier is building the transaction and recovery layer for autonomous labor."

## 9. What we refuse to do now

Do not:
- build a robot;
- train a VLA;
- build robot motion control;
- build a marketplace;
- build a giant Product Shell;
- build enterprise admin;
- create another ledger;
- add speculative schedulers;
- run 30 duplicate reviewers;
- chase publicity before proof;
- claim a billion/trillion-dollar outcome as fact.

## 10. Next concrete milestones

M0 Candidate identity reconciled.
M1 Final source candidate durable.
M2 RUN_1 physical PASS.
M3 RUN_2 physical PASS.
M4 CORE FREEZE.
M5 First paid Continuity Audit.
M6 First paid Founding Pilot.
M7 Positive repeat-use signal.
M8 Product Shell unlocked.
M9 Public Verified Autonomy architecture note.
M10 One physical-AI reference adapter after core + pilot proof.

The order of M5 can overlap M0–M4 because the audit is a service deliverable, not a product-proof claim.

## 11. One metric that keeps the company honest

Primary early business metric:

PAID_GOALS_THAT_RESUME_WITHOUT_FOUNDER_RELAY

It combines:
- real customer;
- real payment;
- real work;
- continuity;
- autonomy;
- outcome.

Everything else is supporting evidence.
