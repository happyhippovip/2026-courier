# Courier Physical AI — Public Thesis Draft

Status: PUBLIC-SAFE DRAFT
Date: 2026-09-28
Rule: Does not change or bypass Courier's current technical gate order.

## Category thesis

Courier is building **Verified Autonomy Infrastructure**.

The long-term problem is larger than keeping one software agent alive.

Autonomous work increasingly crosses:
- models;
- providers;
- machines;
- sessions;
- fleets;
- and eventually physical robot bodies.

The system must preserve the truth of what already happened when the worker changes.

## Public problem statement

A long-horizon autonomous task can fail in a uniquely dangerous state:

the old worker is gone, but its real-world effect may already have happened.

Blind retry can duplicate an effect.
Blind resume can trust stale state.
Starting over can destroy valid progress.

Courier explores a vendor-neutral **Causal Handoff** layer that separates:

- task intent;
- execution identity;
- observed effects;
- evidence;
- causal progress;
- permission to continue.

## Public primitive — Verified Work Transaction

A Verified Work Transaction contains:

CONTRACT
-> IDENTITY
-> EXECUTION
-> OBSERVED EFFECT
-> EVIDENCE
-> VERIFICATION
-> RECONCILIATION
-> NEXT ACTION
-> RECOVERY

For physical systems, command acknowledgement is not equivalent to a verified outcome.

## Public primitive — Continuity Proof Card

A Continuity Proof Card can state:

- what task was authorized;
- which worker/body/runtime acted;
- what result was observed;
- what evidence supports it;
- what remains unknown;
- which next action is authorized;
- whether a human intervened;
- which exact software/policy/runtime was active.

## Public research problem — Causal Handoff Benchmark

A future benchmark should test whether autonomous work can survive interruption and worker replacement without duplicate or unsafe effects.

Example benchmark events:
- interruption during manipulation;
- ambiguous task completion;
- stale worker returns;
- replacement body has different capabilities;
- external world changes during outage;
- restart after a partially completed irreversible action.

Candidate metrics:
- successful continuation rate;
- duplicate-effect rate;
- unsafe-continuation rate;
- stale-authority rejection;
- human interventions;
- evidence cost;
- time to resume;
- provenance completeness;
- cross-embodiment continuation success.

## Ecosystem position

Courier does not aim to replace:
- robot foundation models;
- low-level motion control;
- simulation;
- functional safety;
- fleet-management protocols.

Potential integration position:

robot/model stack
-> safety layer
-> **Courier causal continuity / proof**
-> enterprise workflow and evidence

## Why now

Robot foundation models are rapidly improving long-horizon autonomy and cross-environment generalization.

At the same time:
- deployed fleets create long-tail failures;
- real-world state can diverge from simulation;
- robot stacks are version-sensitive;
- mixed-vendor fleets need interoperability;
- safety/certification requires evidence;
- expert human attention remains expensive.

The public question Courier wants to make legible is:

> How do autonomous systems preserve causal truth and continue unfinished work safely when the worker, runtime, or embodiment changes?

## Scope guard

This is strategic direction, not permission to build robotics before the existing Courier proof gates and real digital pilot evidence are complete.

Current order remains:
candidate reconciliation
-> exact source candidate
-> RUN_1
-> RUN_2
-> Core Freeze
-> minimum real pilot
-> only then bounded physical-AI reference work.
