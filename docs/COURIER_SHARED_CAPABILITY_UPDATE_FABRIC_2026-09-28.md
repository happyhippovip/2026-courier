# Courier Shared Capability + Update Fabric — 2026-09-28

Status: CANONICAL PRODUCT / BUSINESS DIRECTION
Classification: LATER until Core proof + positive pilot signal, except documentation/design preparation.
Purpose: make every verified useful improvement capable of benefiting other Courier users without leaking private customer/project data.

## Product idea

Courier should compound across customers.

If one user creates a genuinely reusable capability — for example:
- a robust pipeline pattern;
- a reusable ingestion/verification workflow;
- a restaurant/pizzeria operations block;
- a proven recovery routine;
- a connector recipe;
- a reusable evaluation/test harness;

Courier should be able to turn that work into a safe, versioned, optional capability that other users can receive.

Example:
Marco builds a useful pipeline.
Sebastian should be able to receive the generalized pipeline capability.
Felix builds a reusable pizzeria module.
Marco and Sebastian should be able to install that optional domain pack if useful.
Improvements should flow both directions.

The transferable unit is a sanitized, generalized, tested capability package — not another customer's private repository, raw prompts, credentials, personal data, proprietary content, or hidden business data.

## Four distribution classes

### 1. CORE_SECURITY_UPDATE

Purpose:
- security fixes;
- critical compatibility;
- update-chain integrity;
- recovery/rollback fixes;
- critical runtime safety.

Default:
strongly recommended / automatic according to user update policy.

Must include:
- signed manifest;
- version;
- source/build identity;
- compatibility metadata;
- rollback path;
- Last Known Good;
- migration/recovery instructions.

### 2. SHARED_CAPABILITY_PACK

Reusable cross-industry capability.

Examples:
- generic CI/release pipeline;
- artifact verifier;
- restart-safe workflow;
- reporting/export component;
- reusable connector abstraction.

Default:
discoverable and optionally auto-recommended.
Installation is user-controlled unless the user explicitly opts into an automatic compatible-capability channel.

### 3. DOMAIN_PACK

Optional industry/use-case capability.

Examples:
- pizzeria/restaurant operational block;
- property-management flow;
- ecommerce catalog flow;
- agency client handoff pack.

Default:
optional.
Never silently added merely because another user created it.

### 4. PRIVATE_PROJECT_ARTIFACT

Customer/project-specific code, data, prompts, credentials, private context, proprietary logic or business records.

Default:
PRIVATE.
Never enters the shared catalog without explicit authority plus a sanitization/generalization review.

## Contribution pipeline

PRIVATE WORK
-> reusable-candidate detection
-> explicit sharing/rights check
-> sanitize/generalize
-> strip customer identifiers/secrets/data
-> provenance/license check
-> deterministic tests/evaluation
-> compatibility contract
-> security review
-> capability fingerprint
-> signed package
-> staged release
-> optional catalog/update distribution
-> telemetry/evidence
-> rollback/revoke if needed

No worker may jump directly from one customer's repo to another customer's repo.

## Shared Capability Registry

Each published capability should have a durable manifest:

CAPABILITY_ID=
NAME=
CATEGORY=
VERSION=
CONTENT_HASH=
SOURCE_PROVENANCE=
LICENSE_OR_RIGHTS=
CREATED_FROM_PRIVATE_WORK=YES|NO
SANITIZATION_REVIEW=
SECURITY_REVIEW=
TEST_EVIDENCE=
COMPATIBILITY=
DEPENDENCIES=
MIN_COURIER_VERSION=
UPDATE_CHANNEL=
INSTALL_POLICY=
ROLLBACK_TARGET=
DEPRECATION_STATE=
REVALIDATION_TRIGGER=

Private contributor/customer identity need not be exposed to recipients.

## Data-saving / bandwidth-saving design

Prefer:
- content-addressed storage;
- deduplication by cryptographic content hash;
- delta/component updates;
- shared immutable artifacts cached once;
- dependency reuse;
- manifest-first update checks;
- download only changed blobs/chunks;
- compression where measurable;
- no repeated download of identical capability versions.

Goal:
use fewer bytes, fewer provider/model calls, and fewer repeated builds while preserving verification.

Measure:
UPDATE_BYTES_DOWNLOADED
UPDATE_BYTES_REUSED
DEDUP_BYTES_SAVED
CAPABILITY_CACHE_HIT
DELTA_UPDATE_RATIO
FAILED_UPDATE_RATE
ROLLBACK_RATE

## Update cadence

The cadence is a product policy, not a promise that code changes every period.

Recommended channels:

### Continuous metadata/security check
Bounded automated check for signed metadata, advisories and revocations.

### Weekly stable update window
Candidate:
- security fixes;
- compatibility fixes;
- high-confidence shared capabilities;
- small improvements with strong evidence.

### Monthly platform rollup
Candidate:
- larger shared capability collection;
- dependency refreshes;
- compatibility migrations;
- broader performance/reliability improvements;
- crypto-readiness changes that passed evidence gates.

Emergency security releases may occur outside schedule when justified.

No release exists merely to satisfy a calendar.

## User choice

Users should control update behavior.

Suggested modes:
- SAFE_AUTO: verified Core/Security updates automatically; optional packs recommended.
- BALANCED: verified Core updates + user-approved shared capability packs.
- PINNED: user/org pins versions and approves changes manually.
- OFFLINE/BUNDLED: signed update bundle imported manually where required.

Optional capabilities can be:
- enabled;
- disabled;
- pinned;
- removed;
- rolled back.

## Time Machine / version history

Courier should maintain a durable update/recovery timeline analogous to a Time Machine for the product state.

Store durably:
- release manifests;
- capability manifests;
- content hashes;
- source/build/runtime identities;
- migration versions;
- compatibility state;
- update decisions;
- install results;
- rollback targets;
- Last Known Good references;
- Proof Cards/evidence references.

Do NOT store in the public Courier repository:
- customer secrets;
- private customer data;
- raw private repositories;
- private account information.

Repository should contain the architecture, schemas, release policy, public manifests/templates and code.
Private/customer-specific state belongs in authorized private/durable stores.

## Update-chain security

Every production update path should eventually support:
- signed release metadata;
- hash verification;
- provenance;
- reproducible/verifiable builds where practical;
- staging;
- atomic activation;
- rollback;
- Last Known Good;
- state compatibility;
- revocation;
- no lost in-flight work.

Shared capability installation must obey the same integrity model.

## Cryptographic and post-quantum direction

Each release should be an opportunity to improve cryptographic posture when evidence and platform support justify it.

Required principles:
- crypto agility;
- algorithm/version inventory;
- migration-ready formats;
- replaceable signing/key-exchange primitives;
- backwards/forwards compatibility strategy;
- tested rollback;
- standards-based implementations;
- explicit deprecation schedule;
- post-quantum migration readiness.

Do NOT market or claim "quantum secure" merely because a post-quantum algorithm is mentioned or experimented with.

A stronger claim requires a concrete, implemented, interoperable and tested cryptographic profile.

Preferred language:
"crypto-agile and post-quantum migration ready" until stronger evidence exists.

## Business model / moat

The shared capability fabric creates a compounding product loop:

MORE REAL USERS
-> MORE PROVEN WORKFLOWS
-> MORE GENERALIZABLE CAPABILITIES
-> BETTER SHARED LIBRARY
-> LESS WORK / DATA / SETUP PER USER
-> BETTER OUTCOMES
-> MORE USERS

Business advantages:
- lower setup/support cost;
- lower repeated engineering cost;
- lower bandwidth/build duplication;
- faster time to value;
- stronger retention;
- shared improvement without forcing data pooling;
- capability packs can later support differentiated packaging/pricing if validated.

The moat is not "we collect everyone's data."
The moat is "we turn authorized, proven reusable solutions into safe reusable product capabilities."

## Privacy / IP / rights

Before a private artifact becomes shared:
- confirm right to share/generalize;
- remove secrets and identifiers;
- remove customer/private datasets;
- verify licensing/provenance;
- evaluate for hidden project-specific assumptions;
- provide a revocation/update path where appropriate.

Opt-in to sharing is distinct from opt-in to receiving shared capabilities.

A user may:
- contribute nothing and still receive public/official capabilities;
- contribute selected generalized capabilities;
- decline optional capability packs;
- pin/disable updates according to product policy.

## Product sequencing

This direction is durable product strategy, but implementation must respect Finish Before Expansion.

Before Core + positive pilot signal:
- architecture/docs/manifests may be designed;
- no giant marketplace;
- no uncontrolled cross-customer distribution;
- no update infrastructure that destabilizes current proof.

After Core + pilot signal:
1. signed safe updater;
2. release/rollback/Time-Machine state;
3. capability manifest format;
4. local/shared capability registry;
5. delta/content-addressed distribution;
6. opt-in sharing + receiving policies;
7. weekly stable channel;
8. monthly rollup channel;
9. measured capability reuse;
10. broader catalog only after safety/usefulness evidence.

## Permanent principle

Every useful update should ask:

1. Does this make Courier safer or more reliable?
2. Can this improvement be generalized safely?
3. Can users receive it without exposing another user's data?
4. Can we distribute only the changed bytes/components?
5. Can it be rolled back?
6. Does it improve crypto agility / future migration readiness where relevant?
7. Can the user choose whether optional capability packs are installed?
8. Is the update bound to evidence and a durable fingerprint?

If yes, preserve the improvement as reusable product memory instead of solving the same problem independently for every customer.
