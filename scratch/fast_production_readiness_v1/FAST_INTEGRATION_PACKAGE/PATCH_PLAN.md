# PRODUCTION COURIER PATCH PLAN: FAST PRODUCTION READINESS V1

## 1. Executive Summary
This patch plan integrates the 5 critical autonomy choke points proven in `scratch/fast_production_readiness_v1` into the production Courier repository (`C:\Users\lol\2026-workspace\courier`).
All changes have undergone dual-suite empirical verification (45 backward-compatible P0 supervisor tests + 19 mandatory readiness scenario tests) with a 100% pass rate.

## 2. Target Files in Production
1. `courier/supervisor/no_stacking.js` (GAP-001: ResourceLockManager)
2. `courier/supervisor/lease_manager.js` (GAP-002: Process identity tuple & fail-closed destruction)
3. `courier/supervisor/decision_engine.js` (GAP-004: BorderGuard & GAP-003: CompletionGovernor)
4. `courier/supervisor/progress_tracker.js` (GAP-005: ResultCustoms & EvidenceVerifier)
5. `courier/supervisor/index.js` (Unified exports of new choke points)
6. `courier/supervisor/governance/` (Runtime governance modules)
7. `courier/supervisor/core/` (Runtime core state machines and projection primitives)

## 3. Layered Integration Sequence
Following the verified acyclic dependency graph:

### Step 0: Dependency Bundle Placement
- Copy `FAST_INTEGRATION_PACKAGE/SHADOW_PATCH/bundle/governance/` to `courier/supervisor/governance/`.
- Copy `FAST_INTEGRATION_PACKAGE/SHADOW_PATCH/bundle/core/` to `courier/supervisor/core/`.

### Step 1: Layer 0 — Core Mutex & Identity Primitives
- **Apply Patch 01 (`no_stacking.js`)**:
  - Replaces string equality lock checking with `ResourceLockManager`.
  - Implements Windows NTFS case-folding (`toLowerCase()`, path normalization).
  - Implements hierarchical subpath locking (parent blocks child, child blocks parent, independent siblings permitted).
- **Apply Patch 02 (`lease_manager.js`)**:
  - Enhances process identity to composite tuple `(PID, START_TIME, TASK_TOKEN)`.
  - Implements `safeTerminateProcess` with start-time drift validation ($pm 2000$ms).
  - Enforces invariant: `UNKNOWN` process identity never authorizes kill (`can_terminate: false`).

### Step 2: Layer 1 — Pre-Dispatch Gate
- **Apply Patch 03 (`decision_engine.js`)**:
  - Integrates `BorderGuard.evaluatePreDispatch()`.
  - Verifies lock availability via `ResourceLockManager` and stamps `TaskPassport` before worker dispatch.

### Step 3: Layer 2 — Post-Execution Gate
- **Apply Patch 04 (`progress_tracker.js`)**:
  - Integrates `ResultCustoms` and `EvidenceVerifier`.
  - Validates exit code, passport signature, and computes SHA-256 disk checksums of all declared output artifacts.

### Step 4: Layer 3 — Mission Governance
- **Configure `CompletionGovernor` in `decision_engine.js`**:
  - Worker global completion claims (`status=DONE`) are explicitly stripped of authority.
  - Global mission completion is determined strictly by the supervisor after all constituent sub-tasks satisfy `ResultCustoms`.

### Step 5: Index Exports
- **Apply Patch 05 (`index.js`)**:
  - Exports `ResourceLockManager`, `BorderGuard`, `ResultCustoms`, `EvidenceVerifier`, and `CompletionGovernor`.

## 4. Acceptance Criteria
1. Full test suite executes cleanly with 0 failures.
2. Production code changes are confined strictly to `courier/supervisor/`.
3. Financial spend remains strictly €0.00.
4. Git working tree is clean and ready for human commit.
