# FINAL ADVERSARIAL REVIEW: TOP 10 RISKS OF POST-FREEZE INTEGRATION

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Core Question**: *"If we applied these four specs tomorrow, what could cause us to make Courier LESS safe?"*

---

## ATTACK 1: OVERLOCKING
- **Threat**: Broad resource declarations (e.g. `tree:/` or `tree:src/`) globally serialize otherwise independent tasks, paralyzing system throughput.
- **Defense**: Fine-grained sub-tree declaration guidelines (`tree:src/moduleA/`) combined with prefix lookalike non-collision (`src/core/` does not collide with `src/core_v2/`). `tree:/` is reserved strictly as a pessimistic fallback for untyped legacy tasks during migration.

---

## ATTACK 2: DEADLOCK
- **Threat**: Two workers acquire multiple resources in opposite orders ($T_1$ acquires $R_A$ then $R_B$; $T_2$ acquires $R_B$ then $R_A$), creating circular wait.
- **Defense**: Atomic multi-resource acquisition with canonical lexicographical ordering. `acquireLocks()` sorts canonical resource keys before locking and performs an all-or-nothing check. If any resource is contested, zero locks are granted, completely eliminating circular wait.

---

## ATTACK 3: PERMANENT HOLD (LIVENESS PARALYSIS)
- **Threat**: Tasks entering `EXECUTION_UNCERTAIN` remain stuck indefinitely, causing autonomous operations to stall.
- **Defense**: While automatic redispatch is strictly forbidden, Courier generates a structured `ChiefEscalationEnvelope` with diagnostic bundle references and an automated settlement probe. If external evidence confirms non-effect (e.g. git tree unmodified, transaction ID absent in external ledger), human or authenticated settlement tool can transition state to `SETTLED_ABORTED` to release the hold safely.

---

## ATTACK 4: APPROVAL FALSE POSITIVES
- **Threat**: A user says "weiter" or answers an unrelated question, and Courier interprets the message as approving a pending financial payment.
- **Defense**: "weiter" is strictly rejected. Approval requires a cryptographically signed, single-use approval token containing `nonce`, exact `task_id`, exact `task_version`, and `maximum_liability_eur`. A conversational response cannot satisfy the capability barrier.

---

## ATTACK 5: LOST HISTORICAL TASKS
- **Threat**: Schema migration mutates or corrupts old task records or deletes terminal leases.
- **Defense**: Migration is strictly append/enrich only. Legacy tasks retain their original identifiers, logs, and completion states. Terminal `COMPLETE` tasks are archived as read-only.

---

## ATTACK 6: LEASE NEVER RELEASED (ZOMBIE LOCKS)
- **Threat**: A worker process crashes hard without calling `release()`, leaving locks permanently held.
- **Defense**: `ProcessLeaseManager` binds locks to lease heartbeats and process liveness. When `RestartReconciler` or `TaskHygiene` verifies process death, locks associated with the lease are cleanly reclaimed.

---

## ATTACK 7: MIGRATION AMBIGUITY & IN-FLIGHT SPLIT
- **Threat**: A crash occurs while migrating durable state, leaving half the tasks in v1 schema and half in v2.
- **Defense**: Atomic two-phase write pattern (`leases.json.migrating.tmp` -> checksum verify -> atomic rename). On reboot, any incomplete `.tmp` file is safely discarded and migration re-executed.

---

## ATTACK 8: PROCESS IDENTITY FALSE NEGATIVES
- **Threat**: Legitimate worker running on macOS has slightly drifted clock or Darwin API returns `EPERM`, causing Courier to assume worker is dead and restart work.
- **Defense**: Clock tolerance window of $\pm 1000\text{ms}$ accommodates OS tick jitter. On `EPERM` or missing metadata, the reconciler transitions to `UNKNOWN` — and under `UNKNOWN`, **assuming dead is strictly forbidden**; Courier continues passive monitoring via file/progress evidence.

---

## ATTACK 9: CENTRAL DISPATCHER BYPASS
- **Threat**: A rogue worker or subagent directly spawns a subprocess or connects to a tool without going through `CourierDispatcher.dispatch()`.
- **Defense**: Tool runner execution layer requires an authenticated, signed lease token passed in the environment context. Tools check lease validity before executing mutative commands.

---

## ATTACK 10: ROLLBACK RESTORING UNSAFE SEMANTICS
- **Threat**: Operational rollback reverts A01 code, causing previously held `EXECUTION_UNCERTAIN` tasks to suddenly redispatch and duplicate effects.
- **Defense**: Rollback specification mandates that task state values are immutable: reverting code does not alter `task.state = 'EXECUTION_UNCERTAIN'`. The supervisor blueprint invariant continues to hold.
