# Hard No-Idle Operator Layer — 2026-09-28

Status: CANONICAL OPERATOR PROTOCOL
Authority: COURIER OPERATIONAL CONTROL
Host Architecture: macOS (`Darwin 25.6.0 x86_64`) / Windows (`Windows 11 / Server 2022`)
Providers: Google Antigravity CLI (`C1`), Anthropic Claude (`Opus 4.6 / Sonnet 5`), OpenAI ChatGPT (`Muse`)

---

## 1. Principles of the Hard No-Idle Policy

1. **Non-Terminal Idle States**:
   - `SLOT_IDLE=YES` is an internal state indicator, NEVER a terminal stopping condition during a target run window (e.g. 8-hour target).
   - `TRUE_IDLE` means local queues are drained, requiring immediate replenishment from durable unfinished work or fallback backlogs.
   - `FAMILY_COMPLETE` indicates that one specific milestone family (e.g. W1, W2, or a batch of 24 prompts) has finished, but the global mission continues across subsequent backlog families.

2. **Autonomous Replenishment Loop**:
   - **HARVEST**: Reconcile completed tasks, verify hashes, index artifacts.
   - **CLAIM**: Atomically claim one unique READY task in `ops/ai/wall_claims/`.
   - **REUSE**: Check existing proof fingerprints before re-executing.
   - **EXECUTE**: Run deterministic checks, generate specifications, or assemble proof records within exact bounded scope.
   - **PERSIST**: Store deliverables and result manifests in `ops/ai/wall_results/`.
   - **RECONCILE**: Append cryptographically linked blocks to `ops/ai/wall_ledger/ledger.db`.
   - **RELEASE**: Mark claim as RECONCILED.
   - **REPLENISH**: When current queue drains, advance to the next priority backlog.

3. **Fallback Backlog Priority Matrix**:
   1. `mac_finish24` packets and physical proof deliverables.
   2. Mac physical-proof prep queue (`M181..M260`).
   3. Runtime, source, build, and config binding.
   4. Artifact, hash, and event evidence.
   5. Process, port, state, and log ownership.
   6. Restart and no-replay idempotency matrix.
   7. Proof Card fields and evidence collation.
   8. Core Freeze candidate-independent fields.
   9. Cross-host, provider, and session continuity.
   10. Result cache, claim lease, and harvest integrity.
   11. Resource management and anti-tight-polling guards.
   12. Post-freeze pilot onboarding and telemetry prep.
   13. Shared capability and update fabric preparation.

---

## 2. Gate Separation & Physical Run Restraints

- **Pre-Codex Gate**: If `GATE_STATE_CURRENT.md` reports `PRE_CODEX_STATE=DURABILITY_PENDING`, only the designated gate persistence owner handles candidate binding; all other workers execute candidate-independent prep work.
- **Physical Run Restraints**:
  - `RUN_1` is strictly forbidden until `READY_FOR_PHYSICAL_RUN=YES`.
  - `RUN_2` is strictly forbidden until `RUN_1 PASS` is attested with zero human relays.
- **Central Writer Authority**: Application source files in `server/`, `scripts/`, `tests/` remain under Windows Central Writer authority.
