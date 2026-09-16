# MIGRATION SPECIFICATION — COURIER POST-FREEZE INVARIANTS

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Scope**: Migration of durable leases, task records, and safety ledgers to support A01, L01, G01, and B01.

---

## 1. MIGRATION INVARIANTS
1. **Never Mutate Historical Task Identity**: Task IDs, timestamps, and terminal audit logs are immutable.
2. **Never Convert UNKNOWN to Safe**: Missing security-critical fields default to `UNKNOWN` or `HOLD`, never to `PERMITTED`.
3. **Never Convert EXECUTION_UNCERTAIN to Retryable**: In-flight tasks interrupted during migration must remain `EXECUTION_UNCERTAIN`.
4. **Never Create Approval from Absence**: Legacy tasks requiring financial capability that lack an approval token MUST NOT be treated as approved.
5. **Never Release Writer Leases Blindly**: If a lease lacks new multi-factor identity fields, it must not be released prematurely or marked dead without verification.

---

## 2. STATE-BY-STATE TRANSITION MATRIX DURING MIGRATION

| Existing Durable Task State | Incoming Data Schema Delta | Safe Migration Action | Post-Migration Operational State | Rationale |
|---|---|---|---|---|
| **PROPOSED** | Lacks `declared_resources` | Default to `declared_resources: ['legacy:unspecified_scope']`. | `PROPOSED` | Unspecified scope runs sequentially under single-writer safe mode. |
| **STAMPED** | Lacks `execution_uncertain` | Default `execution_uncertain: false`, `side_effect_uncertainty: false`. | `STAMPED` | Task has not dispatched yet; no side effects could have occurred. |
| **DISPATCHED** | Lacks `process_start_time` & `task_token` | If restart occurred during dispatch, flag `EXECUTION_UNCERTAIN`. If live, flag `identity_status: 'UNKNOWN'`. | `HOLD_UNCERTAIN` or `IN_FLIGHT (SUPERVISED_CONSERVATIVE)` | Cannot distinguish whether worker started before or after migration. |
| **IN_FLIGHT** | Lacks `declared_resources` & `start_time` | Maintain existing lease until process exits. Do not kill. Mark `declared_resources: ['tree:/']` (pessimistic lock). | `IN_FLIGHT` | Prevents subsequent tasks from colliding with legacy un-scoped active writer. |
| **PENDING_VERIFY** | Lacks `approval_nonce` | Retain result verification; if task was financial, require human confirmation before release. | `PENDING_VERIFY` | Result Customs verifies deliverables normally. |
| **BLOCKED** | Lacks new resource lock fields | Keep blocked until dependencies resolve. | `BLOCKED` | Preserves dependency order. |
| **HUMAN_GATE** | Lacks structured `approval_token` schema | Do NOT auto-approve. Require generation of modern single-use approval token upon human sign-off. | `HUMAN_GATE` | Absence of token cannot satisfy new security gate. |
| **EXECUTION_UNCERTAIN** | Lacks new `side_effect_potential` field | Set `execution_uncertain: true`, `side_effect_potential: 'POSSIBLE_UNSETTLED'`. | `EXECUTION_UNCERTAIN` (FENCE LOCKED) | A01 fence dominates immediately; auto-redispatch blocked permanently. |
| **COMPLETE** | Lacks all new fields | Read-only archival. **DO NOT MUTATE**. | `COMPLETE` (ARCHIVED) | Terminal immutable historical evidence; zero operational risk. |

---

## 3. LEGACY RECORD HANDLING
When loading a legacy `leases.json` or `tasks.json`:
```javascript
function migrateLegacyLease(legacyLease) {
  return {
    ...legacyLease,
    schema_version: 2,
    // B01 fields
    process_start_time_epoch_ms: legacyLease.process_start_time_epoch_ms ?? null,
    task_token: legacyLease.task_token ?? 'LEGACY_UNSET_TOKEN',
    identity_resolution_mode: legacyLease.process_start_time_epoch_ms ? 'MULTI_FACTOR' : 'LEGACY_CONSERVATIVE_UNKNOWN',
    // L01 fields
    declared_resources: Array.isArray(legacyLease.declared_resources) && legacyLease.declared_resources.length > 0
      ? legacyLease.declared_resources
      : ['tree:/'], // Pessimistic repository-wide lock for un-scoped legacy tasks
    // A01 fields
    execution_uncertain: legacyLease.status === 'EXECUTION_UNCERTAIN' || legacyLease.execution_uncertain === true,
    side_effect_uncertainty: legacyLease.side_effect_uncertainty ?? (legacyLease.status === 'EXECUTION_UNCERTAIN'),
    migrated_at: new Date().toISOString()
  };
}
```

---

## 4. CRASH DURING MIGRATION RECOVERY SPECIFICATION
1. **Crash BEFORE Migration**:
   - Migration script has not run. System restarts into old code or re-runs migration script.
   - *Result*: Clean; no partially written files.
2. **Crash MID-MIGRATION**:
   - Migration uses the **Atomic Two-Phase Write Pattern**:
     1. Read `leases.json` -> Write `leases.json.migrating.tmp`.
     2. Verify checksum and syntax of `leases.json.migrating.tmp`.
     3. Atomic rename `leases.json.migrating.tmp` -> `leases.json`.
   - If crash occurs mid-write, `leases.json.migrating.tmp` is abandoned, and original `leases.json` remains untouched.
   - On startup, Reconciler detects orphaned `.migrating.tmp`, logs a warning, and safely re-triggers migration.
3. **Crash AFTER Migration BEFORE Code Activation**:
   - Data is schema version 2; code is version 1.
   - Code version 1 safely ignores extra fields (`declared_resources`, `task_token`, `start_time`).
   - *Result*: Zero regression.
4. **Crash AFTER Code Activation BEFORE Verification**:
   - Code version 2 restarts and loads schema version 2 data.
   - RestartReconciler detects in-flight tasks and enforces A01 uncertainty fence on any unproven dispatches.
   - *Result*: 100% deterministic, fail-closed recovery.
