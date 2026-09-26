# Courier V1 — Capacity, Updates, and Cryptographic Readiness Plan

Status: PRODUCT GOAL / LATER THAN CURRENT CORE PROOF

## V1 capacity selector

Courier V1 should expose an exact logical wall-size selector for **every integer from 1 through 64**.

This is a requested capacity value, not a promise that 64 resident/heavy processes will run.

Runtime admission remains governed by:

- host resources
- provider quota
- cost budget
- dependencies
- writer ownership
- safety gates

A requested 64 may truthfully become, for example:

Requested 64
Admitted 12
Active 9
Waiting 3
Guarded 52

## Free package

Initial free-package product concept:

- make very small wall sizes easy and useful, especially 1 / 2 / 3;
- preserve the same simple selector model as higher-capacity use;
- final entitlement/cost/provider limits are TBD and must not be invented before product/billing evidence exists.

The UI architecture should not require a redesign when larger exact capacities up to 64 are enabled.

## Automatic update experience

Desired experience: simple, fast, game-like update convenience without a heavyweight patching system.

At application/host boot:

1. check signed update metadata;
2. determine whether a newer compatible version exists;
3. fetch only required changed package/artifact data where feasible;
4. verify signature/hash before install;
5. stage safely;
6. retain rollback/recovery path;
7. start the verified version;
8. report version + update result truthfully.

The user should not manually copy patch files between machines.

## Daily update cadence

Courier may check for updates daily.

"Daily" means check cadence, not guaranteed code release every day.

No update should be published merely to create activity.

## Safety-review agents

A bounded daily review lane may inspect whether Courier can become safer, simpler or more resilient.

Allowed examples:

- dependency/security advisories
- unsafe process-control patterns
- signing/update-chain integrity
- secret handling
- permission boundaries
- cryptographic deprecations
- post-quantum migration readiness
- rollback/update failures
- resource-safety regressions

The review produces proposals/evidence; it does not silently rewrite critical security architecture.

## Post-quantum / cryptographic readiness

Courier should track credible standards and library/platform support for post-quantum cryptography.

Rules:

- never market "quantum secure" without a concrete proven cryptographic profile;
- prefer established standards and maintained platform/library implementations;
- maintain cryptographic agility so algorithms can be replaced without redesigning the whole product;
- inventory where public-key cryptography is used: update signing, TLS, identity, artifact signatures, secrets exchange;
- migrate only with interoperability/testing/rollback evidence;
- record UNKNOWN when platform/provider support is not proven.

Goal:

**quantum-readiness through crypto agility and evidence**, not speculative claims.

## Patch-size principle

Courier has no giant game maps/assets, so most releases should be capable of being much smaller than game-content patches.

Still, patch size depends on packaged binaries/dependencies and must be measured, not assumed.

Prefer:

- delta or component updates where safe;
- signed manifests;
- content-addressed artifacts;
- atomic install/swap;
- rollback;
- no partially-installed state.

## Boot safety

Automatic update must never strand the user in an unusable state.

If update verification/install fails:

- retain last known-good version;
- report failure honestly;
- continue safely when possible;
- avoid retry storms.

## Ordering

This plan does not move ahead of:

FINAL CANDIDATE
-> TARGETED TESTS
-> INDEPENDENT REVIEW
-> RUN_1
-> RUN_2
-> MINIMUM HONEST PRODUCT SURFACE

After core proof, capacity/update work can become a NEXT-phase product lane.
