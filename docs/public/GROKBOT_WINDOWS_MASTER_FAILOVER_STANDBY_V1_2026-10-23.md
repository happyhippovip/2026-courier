# Courier Symphony — Windows GrokBot Master Failover Standby V1
**Public governance-only protocol · October 23, 2026**

> Not a master promotion, not a scheduler installation, not a writer lease, not a merge approval. A standby agent can be ready without becoming a second active master. Private account balances, files, paths, secrets and runtime telemetry must never be copied into this public document.

## Purpose

The existing GrokBot Windows relay/dispatcher may **become the canonical Master Coordinator if and only if a safe, authorized handover is verifiably complete**. The present Mac/Ultra master remains active until that handover. The standby relay can meanwhile continue to produce private reports, reconcile evidence, validate the workkey ledger and prepare recommendations without claiming authority.

The system must prevent two agents from distributing contradictory tasks, advancing the same workkey, issuing parallel claims, overwriting a checkpoint or performing an unauthorized merge.

## Roles

| Function | Normal mode | Failover mode |
| --- | --- | --- |
| Existing canonical Master (Mac/Ultra) | sole authoritative distributor and owner mapper | relinquishes authority with acknowledged signed/validated state transfer, or objectively loses its valid fenced authority |
| Windows GrokBot | STANDBY/RELAY, private status and proof checking | becomes MASTER **only after verified exclusive authority transfer**, publishes a new epoch to private source of truth |
| Google Antigravity Windows (upper) | CI, PR and event watch using its own existing bounded schedule | remains verifier, does not run a second dispatcher |
| Cursor Windows (lower left) | own authorized implementation/patch/tests | same own writer scope; never inherits master's authority |
| Google Antigravity Windows (lower right) | independent ledger/negative-test verifier | same; no product write without lease |
| L1/HG-02 | reviews promotion/merge gates | retains human gates, even if master changes |

## Safe transition state machine

`STANDBY_READ_ONLY` → `PREPARED` → `AWAIT_TRANSFER` → `MASTER_ACTIVE` → `HAND_BACK_PREPARED` → `STANDBY_READ_ONLY`.

1. **PREPARED:** reconcile the canonical private workkey checkpoint, known owners, running jobs, ledger journal head, latest GitHub SHAs and CI status. Prove the candidate can read the current state; run an independent dry-run allocation **without writing canonical workkeys**. Preserve exact SHA-256 evidence.
2. **AWAIT_TRANSFER:** choose one of two independently evidenced transfer routes:
   - **Planned handover:** current canonical master declares itself suspended, publishes/verifies a release record, and the authorized L1/human releases the corresponding dispatcher authority to the named standby; or
   - **Emergency takeover:** a canonical fencing authority confirms that the previous master's lease/epoch has expired and rejects all of its writes; the designated human or an already approved failover policy authorizes transfer. Merely no chat reply, no bot messages, quota exhaustion, or missed timer does **not** prove a stale writer is fenced.
3. **MASTER_ACTIVE:** only after verified exclusive lease or canonical compare-and-swap grants a new epoch. Record `old_master`, `new_master`, `epoch`, `grant_id`, `fence_proof`, `authority_source`, `workkey_snapshot_sha`, `timestamp`. Confirm the previous master's requests are now rejected. One authoritative workkey/lease store only.
4. **HAND_BACK:** require exactly the same controlled exclusive transition in reverse. Never create overlapping master rights.

**Fail closed:** if a lease service, access permission, epoch or handover proof cannot be independently checked, remain `STANDBY_READ_ONLY`; prepare one private decision packet, do not claim takeover success.

## Normal four-lane operating procedure

- **Windows GrokBot relay:** own local private report pack and a single outgoing Mac-master handoff on an already approved channel. The existing morning-report routine remains. New backup routine only if it is genuinely different in purpose, cost-bounded, and no equivalent already exists.
- **Google Windows upper:** existing `task-214` (if still active) does CI-event-only reads at its already agreed schedule. No second overlapping `/schedule`.
- **Cursor Windows lower left:** receive bounded new *read-only or own leased* P1 tasks; no re-run of completed installer items; focus F-C1 only as L2 recommendation unless exclusive L2 writer lease exists.
- **Google Windows lower right:** review tests against production code, especially `Controller.create_task` and actual `LedgerEngine.submit`/dependency interplay, independently validate new CI and output truth; no extra heavy test job if another Windows agent runs one.

## Readiness checklist (private, refreshed on change)

- `CANONICAL_MASTER_ID`, `MASTER_EPOCH`, `EXCLUSIVE_LEASE_REF`, `FENCING_PROOF` obtained from authoritative channel or else `UNVERIFIED`.
- `LEDGER_JOURNAL_HEAD`, `PRIVATE_WORKKEY_SNAPSHOT_SHA256`, `CURRENT_OWNER_MAP`, `ACTIVE_HOST_JOBS`, `CURRENT_GITHUB_REFS`, `PENDING_HG02`, `NO_DUPLICATES`.
- `BOT_ACCOUNT_COST_MODE`: included quota confirmed before a new model action; no on-demand billing, no auto-upgrade, `UNKNOWN_COST=BLOCK`.
- `HANDOFF_DELIVERY`: `ACKNOWLEDGED` only if actual recipient acknowledged, otherwise `READY_TO_SEND`.
- `BACKUP_READY=YES` only if all read/consistency and cost checks pass; this does **not** mean `MASTER_ACTIVE`.
- Do not expose raw token values, personal recovery archives, credentials, or machine-path secrets.

## Four-hour work objective

Read-only preparation, deterministic role-scope checks, and a real isolated failover dry run with disposable dummy workkeys. Complete an audit artifact proving no double assignment under simulated failure. No authorization to interrupt a live master or run a production failover as a test.

**End of the current bounded batch:** October 24, 2026, at 03:35 Europe/Berlin. A separately authorized scheduled morning report may run at its actual registered time.

## Invariants

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1 per host
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

Do not invent evidence, background continuity, successfully registered routines, reserved costs or automatic master switch-over.
