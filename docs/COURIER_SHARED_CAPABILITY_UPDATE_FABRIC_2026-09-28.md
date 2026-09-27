# Courier Shared Capability + Update Fabric — 2026-09-28

Status: CANONICAL PRODUCT / BUSINESS DIRECTION
Classification: LATER until Core proof + positive pilot signal, except documentation/design preparation.

## Product idea

Courier should compound across customers.

If one user creates a genuinely reusable capability — for example a robust pipeline, a reusable verification workflow, a restaurant/pizzeria operations block, a recovery routine, a connector recipe, or a test harness — Courier should be able to turn the reusable portion into a safe, versioned capability that other users can optionally receive.

Example:
- Marco builds a useful pipeline.
- Sebastian may receive the generalized pipeline capability.
- Felix builds a reusable pizzeria module.
- Marco and Sebastian may install that optional domain pack if useful.
- Improvements can flow both directions.

The transferable unit is a sanitized, generalized, tested capability package — never another customer's private repository, raw prompts, credentials, personal data, proprietary content, or hidden business data.

## Distribution classes

1. CORE_SECURITY_UPDATE
   Security, compatibility, recovery and update-chain fixes. Signed, versioned, rollback-capable.

2. SHARED_CAPABILITY_PACK
   Reusable cross-industry capabilities such as generic pipelines, artifact verification, reporting/export, restart-safe workflows or connector abstractions.

3. DOMAIN_PACK
   Optional use-case capabilities such as restaurant/pizzeria, property-management, ecommerce or agency workflows.

4. PRIVATE_PROJECT_ARTIFACT
   Customer-specific code, data, prompts, credentials, private context and proprietary logic. Private by default and never cross-distributed automatically.

## Contribution pipeline

PRIVATE WORK
-> reusable-candidate detection
-> explicit sharing/rights check
-> sanitize/generalize
-> strip identifiers/secrets/private data
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

No worker may jump directly from one customer's repo into another customer's repo.

## Capability manifest

Each published capability should bind at least:

CAPABILITY_ID
NAME
CATEGORY
VERSION
CONTENT_HASH
SOURCE_PROVENANCE
LICENSE_OR_RIGHTS
SANITIZATION_REVIEW
SECURITY_REVIEW
TEST_EVIDENCE
COMPATIBILITY
DEPENDENCIES
MIN_COURIER_VERSION
UPDATE_CHANNEL
INSTALL_POLICY
ROLLBACK_TARGET
DEPRECATION_STATE
REVALIDATION_TRIGGER

## Data-saving design

Prefer:
- content-addressed storage;
- cryptographic deduplication;
- shared immutable artifacts cached once;
- dependency reuse;
- manifest-first update checks;
- delta/component updates;
- compression where measured useful;
- no repeated download of identical capability versions.

Measure:
UPDATE_BYTES_DOWNLOADED
UPDATE_BYTES_REUSED
DEDUP_BYTES_SAVED
CAPABILITY_CACHE_HIT
DELTA_UPDATE_RATIO
FAILED_UPDATE_RATE
ROLLBACK_RATE

## Update cadence

The cadence is a release policy, not a promise to ship filler.

- bounded continuous metadata/security/advisory checks;
- weekly stable update window for high-confidence fixes/capabilities;
- monthly platform + capability rollup for larger improvements and migrations;
- emergency security release outside schedule when justified.

No release exists merely to satisfy a calendar.

## User choice

Suggested update modes:
- SAFE_AUTO: verified Core/Security updates automatic; optional packs recommended.
- BALANCED: verified Core updates plus user-approved shared capability packs.
- PINNED: user/org pins versions and approves changes.
- OFFLINE/BUNDLED: signed bundles imported manually where required.

Optional capabilities can be enabled, disabled, pinned, removed and rolled back.

Receiving shared capabilities and contributing capabilities are separate choices.

## Time Machine / durable release history

Courier should retain a Time-Machine-style history of:
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

The public Courier repo should contain architecture, schemas, public manifests/templates, code and release policy — not customer secrets, private repositories, private account data or raw customer datasets.

## Update-chain security

Production update paths should eventually support:
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

Shared capability installation follows the same integrity model.

## Crypto / post-quantum direction

Each release is an opportunity to improve cryptographic posture when standards and platform support justify it.

Principles:
- crypto agility;
- algorithm/version inventory;
- migration-ready formats;
- replaceable signing/key-exchange primitives;
- compatibility strategy;
- tested rollback;
- standards-based implementations;
- explicit deprecation;
- post-quantum migration readiness.

Do not claim "quantum secure" merely because a post-quantum algorithm is mentioned. A stronger claim requires a concrete implemented, interoperable and tested cryptographic profile.

Preferred language until then:
"crypto-agile and post-quantum migration ready."

## Business model / moat

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
- future differentiated packaging/pricing for proven capability packs.

The moat is not "we collect everyone's data."
The moat is "we turn authorized, proven reusable solutions into safe reusable product capabilities."

## Product sequencing

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

## Permanent questions for every useful update

1. Does this make Courier safer or more reliable?
2. Can this improvement be generalized safely?
3. Can users receive it without exposing another user's data?
4. Can we distribute only changed bytes/components?
5. Can it be rolled back?
6. Does it improve crypto agility / migration readiness where relevant?
7. Can the user choose whether optional packs are installed?
8. Is it bound to evidence and a durable fingerprint?

If yes, preserve the improvement as reusable product memory instead of solving the same problem independently for every customer.
