# Courier Symphony — Domain Assurance Profiles

Status: **PRODUCT PRINCIPLE / FUTURE-COMPATIBILITY CONTRACT**

Courier must not treat every automation task as if it had the same consequence model.

The core remains one durable automation kernel:
- canonical append-only ledger;
- deterministic projections;
- fenced dispatch/attempt/result identity;
- fail-closed verification;
- bounded workers;
- exactly-once effect protection;
- recovery/reconciliation;
- Human Desk for unresolved consequential ambiguity.

Above that kernel, Courier may select a **Domain Assurance Profile**.

A profile changes the proof obligations, authorization gates, retry/recovery rules, evidence requirements, and human-control requirements for a task. It does **not** create a second source of truth and does not replace applicable regulation/certification.

## 1. Profile selection

Profile selection is based on declared task context and consequence, not on model intuition alone.

Inputs may include:
- intended use;
- physical actuation;
- human proximity;
- patient impact;
- flight/airborne impact;
- external financial/legal effect;
- reversibility;
- idempotency;
- regulatory jurisdiction;
- required evidence/certification basis.

If the correct profile is ambiguous and the consequence could be high:
**fail closed -> Human Desk / owner confirmation.**

No high-consequence profile is silently downgraded to GENERAL.

## 2. Shared assurance kernel

Every profile inherits:

1. DURABLE INTENT
2. CANONICAL LEDGER
3. FENCED EXECUTION
4. VERIFIED COMPLETION
5. CONSEQUENCE-AWARE RETRY
6. RESTART/REPLAY
7. RESOURCE-AWARE AUTONOMY
8. EXPLAINABLE STATUS
9. HUMAN ESCALATION
10. CHANGE IMPACT RECORD

The profile may only make these stricter.

## 3. GENERAL profile

For ordinary digital automation with reversible or low-consequence effects.

Typical policy:
- normal verifier contract;
- deterministic idempotency where possible;
- bounded retries;
- Human Desk on ambiguous non-idempotent effects.

## 4. ROBOTICS profile

Robotics adds physical-world hazards that software-only automation does not have.

Courier Robotics should distinguish at least:
- industrial fixed robot;
- collaborative robot application;
- autonomous mobile robot / driverless industrial truck;
- remote teleoperation;
- safety-rated motion vs non-safety supervisory logic.

Relevant current standards include ISO 10218-1:2025 for industrial robot safety and ISO 3691-4:2023 for driverless industrial trucks / AMR-like systems.

Profile requirements should include:
- explicit physical-action envelope;
- workspace/zone identity;
- human-presence assumptions;
- speed/force/motion limits supplied by the certified system;
- independent emergency-stop / safety system boundary;
- watchdog/heartbeat with fail-safe stop semantics;
- stale-command rejection;
- command sequence/fencing;
- no blind retry of uncertain motion;
- exact ownership of motion command/result;
- simulator/digital-twin evidence where appropriate;
- physical confirmation when a commanded action has irreversible safety consequence.

Courier must **not** claim that its own software ledger replaces a robot controller's safety-rated functions.

Unique product direction:
Courier can serve as the **assurance/orchestration layer above heterogeneous robot fleets**, while each robot platform retains its certified low-level safety controller.

## 5. MEDICAL profile

Medical automation requires intended-use, patient-risk, lifecycle, human-factors, cybersecurity, and change-control discipline.

Relevant current sources include:
- IEC 62304 software life-cycle processes;
- ISO 14971:2019 risk management, confirmed current in 2025;
- FDA 2023 guidance for device software-function premarket documentation;
- FDA 2025 final guidance for AI-enabled device Predetermined Change Control Plans (PCCPs);
- FDA 2026 final cybersecurity guidance;
- FDA 2026 human-factors marketing-submission guidance.

Profile requirements should include:
- intended-use boundary;
- patient/population context;
- hazard/risk-control traceability;
- requirements -> verification evidence traceability;
- clinical/performance evidence where applicable;
- human-factors / usability evidence for safety-critical interactions;
- cybersecurity evidence and update policy;
- locked/identified model or algorithm version;
- bounded approved change envelope;
- change-impact assessment before deployment;
- no autonomous learning/update outside an approved change-control plan;
- post-deployment monitoring hooks;
- explicit clinician/operator decision boundaries where required;
- immutable evidence package for each consequential release.

Courier must not represent this profile as regulatory approval.

Unique product direction:
Courier can make an AI-enabled medical workflow **continuously auditable and change-controlled**, with every approved modification linked to its evidence, risk controls, version, and deployment decision.

## 6. AVIATION profile

Aviation requires development assurance tied to safety impact and certification basis.

FAA currently recognizes DO-178C/ED-12C for airborne software through AC 20-115D; FAA also identifies DO-254/ED-80 and ARP4754A-related development-assurance practice for complex airborne systems. EASA maintains an AI Roadmap and evolving human-centric AI assurance work.

Profile requirements should include:
- declared certification/safety basis;
- assurance level / safety impact supplied by the program;
- requirements-to-code/model-to-test traceability as applicable;
- independence requirements for verification where required;
- deterministic configuration/version baselines;
- qualified-tool boundary where relevant;
- partition/interface evidence;
- change-impact analysis;
- reproducible build/evidence package;
- no runtime self-modification of certified behavior unless explicitly covered by the approved assurance/change basis;
- fail-safe handling of uncertain execution;
- operator/flight-crew authority boundaries;
- immutable audit trail for every promoted baseline.

Courier must not invent a DAL or certification classification on its own. The program/certification authority supplies that basis.

Unique product direction:
Courier can be the **cross-tool assurance ledger** that preserves requirement, evidence, baseline, verifier, and change-impact relationships even when engineering tools/providers change.

## 7. Domain policy compiler

Long-term product direction:

User intent + declared domain + consequence metadata
-> selected Assurance Profile
-> generated proof obligations
-> authorization gates
-> worker capabilities
-> retry/recovery policy
-> verification plan
-> Human Desk conditions
-> acceptance evidence bundle

This is more valuable than merely selecting an AI model.

Courier should decide:
**what must be proven before an action is allowed and what must be proven before it is called complete.**

## 8. Proof obligations as first-class objects

A task may have explicit proof obligations such as:

- PO-IDENTITY: result belongs to exact task/attempt/dispatch;
- PO-INTEGRITY: evidence/artifact hash matches;
- PO-FRESHNESS: no stale command/result accepted;
- PO-SAFETY-ENVELOPE: action stayed inside declared safety envelope;
- PO-RISK-CONTROL: required risk controls were active;
- PO-HUMAN-AUTH: required human authorization exists;
- PO-CHANGE-BOUNDARY: modification is inside approved change envelope;
- PO-TRACEABILITY: requirement/change -> evidence chain is complete;
- PO-RECOVERY: restart/replay preserves the same final truth.

Only satisfied obligations permit promotion to the next lifecycle state.

## 9. Domain-specific recovery

Recovery policy is profile-dependent.

GENERAL:
bounded safe retry when idempotent.

ROBOTICS:
uncertain physical motion -> stop/reconcile; never reissue blindly.

MEDICAL:
uncertain consequential clinical/device effect -> hold, preserve evidence, require authorized review according to the intended-use workflow.

AVIATION:
uncertain certified-system effect/change -> hold at the assurance boundary; no silent promotion or dynamic behavior change outside approved process.

## 10. Assurance evidence graph

Courier's long-term differentiator should be an evidence graph anchored in the canonical ledger:

INTENT
-> REQUIREMENT
-> RISK / HAZARD
-> CONTROL
-> AUTHORIZATION
-> EXECUTION
-> RESULT
-> VERIFICATION
-> ACCEPTANCE
-> CHANGE IMPACT
-> RELEASE / DEPLOYMENT

Different domains populate different nodes, but the orchestration model stays coherent.

## 11. Daily uniqueness / improvement rule

Every day, harvest real friction from development or customer workflows.

A proposed improvement is accepted only if it strengthens at least one of:
- proof;
- safety;
- recovery;
- traceability;
- operator understanding;
- resource efficiency;
- cross-provider portability;
- domain assurance.

Do not add novelty for novelty's sake.

Prefer innovations that let Courier make a **better consequential decision**:
- run;
- wait;
- retry;
- verify;
- escalate;
- block;
- reconcile;
- promote.

## 12. V1 scope boundary

This document does not expand current Windows V1 implementation scope.

Locked route remains:
ACTIVE LEDGER
-> RELIABLE AUTOMATION
-> GOLDEN PATH
-> DESKTOP HUB
-> WINDOWS EXE
-> CLEAN-MACHINE ACCEPTANCE
-> REAL ADAPTERS
-> DESKTOP ROBOT OVERLAY

Near-term V1 work should preserve the primitives these future profiles need:
- effect_class;
- durable identity/fencing;
- fail-closed verifier;
- Human Desk;
- deterministic replay;
- evidence/artifact hashes;
- explicit BLOCKED states;
- bounded resource ownership.

Domain-specific regulated implementations come later and require domain experts, applicable standards, validation, and certification/regulatory work.

## 13. Fail-safe extension rule

Any future effect class or assurance profile must default to the strict path.

Kernel rule:

**only effects explicitly proven/declared idempotent may enter automatic retry.**

Unknown or newly-added effect classes must not inherit retryability by omission.

Examples of future classes that must not silently become retry-safe:
- physical actuation;
- medical/device consequence;
- aviation/flight consequence;
- legal/financial external effect.

Likewise, consequential human reconciliation must be represented by durable actor-attributed events rather than hidden state mutation.

This rule should be preserved before those domains are implemented.
