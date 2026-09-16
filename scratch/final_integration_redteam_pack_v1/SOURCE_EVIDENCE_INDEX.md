# SOURCE EVIDENCE INDEX — INTEGRATION RED-TEAM PACK V1

This index cross-references all historical sealed evidence from Windows Labs (V2, V3, High-Value Sweep V1, Final 4PCT Adversarial Sweep V1, Nightshift V5) and the Independent Codex Review against the current Windows Courier source tree.

### Operational Invariants
- Read-only analysis of existing Courier production codebase.
- Never silently promote a synthetic lab result into production truth.
- Evidence classifications strictly adhere to:
  - `PROVEN_IN_WINDOWS_LAB`
  - `ARCHITECTURAL_REQUIREMENT`
  - `LIKELY_PRODUCTION_DEFECT`
  - `PRODUCTION_CODE_CONFIRMED`
  - `MAC_NATIVE_PROOF_REQUIRED`
  - `UNKNOWN`

---

## CANDIDATE INVARIANTS SUMMARY

| Candidate | Title | Primary Source Artifact | Counterexample Artifact | Windows Lab Status | Codex Review Classification | Current Source Status | Mac Proof Required |
|---|---|---|---|---|---|---|---|
| **A01** | Execution-Uncertainty Fence | `nightshift_adversarial_factory_v5/campaign_01_a01_uncertainty.js` | `final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/A01_uncertain_redispatch.json` | `PROVEN_IN_WINDOWS_LAB` | `LIKELY_PRODUCTION_DEFECT` / `CONFIRMED_ARCHITECTURAL_REQUIREMENT` | `PRODUCTION_CODE_CONFIRMED` (Documented in blueprint, missing in Dispatcher) | **NO** |
| **L01** | Hierarchical & Semantic Scope Locking | `nightshift_adversarial_factory_v5/campaign_02_l01_no_stacking.js` | `final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/L01_hierarchical_escape.json` | `PROVEN_IN_WINDOWS_LAB` | `LIKELY_PRODUCTION_DEFECT` | `PRODUCTION_CODE_CONFIRMED` (Exact string match in `no_stacking.js`) | **NO** |
| **G01** | Deferred Liability & Capability Gate | `nightshift_adversarial_factory_v5/campaign_03_g01_human_gate.js` | `final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/G01_deferred_liability_bypass.json` | `PROVEN_IN_WINDOWS_LAB` | `CONFIRMED_ARCHITECTURAL_REQUIREMENT` / `LIKELY_PRODUCTION_DEFECT` | `PRODUCTION_CODE_CONFIRMED` (`price_eur > 0` naive check in `safety_gates.js`) | **NO** |
| **B01** | Multi-Factor Process Identity & PID Wrap | `nightshift_adversarial_factory_v5/campaign_04_b01_process_identity.js` | `final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/B01_pid_recycling_false_match.json` | `PROVEN_IN_WINDOWS_LAB` | `CONFIRMED_ARCHITECTURAL_REQUIREMENT` / `CONTRACT_AMBIGUITY` | `PRODUCTION_CODE_CONFIRMED` (Single-factor PID match in `reconciliation.js`) | **YES** (`proc_pidinfo` on Darwin) |

---

## DETAILED EVIDENCE SHEETS

### 1. CANDIDATE A01: Execution-Uncertainty Fence
- **Candidate ID**: `DEFECT-A01`
- **Source Artifacts**:
  - `SUPERVISOR_PLANE_ARCHITECTURE.md` (Blueprint Section 3, lines 59-64)
  - `supervisor/reconciliation.js` (lines 104-132)
  - `scratch/nightshift_adversarial_factory_v5/campaign_01_a01_uncertainty.js`
  - `scratch/final_4pct_adversarial_intervention_v1/REPAIRS/REPAIR-01-uncertain-router-lock.js`
- **Counterexample Artifact**:
  - `scratch/final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/A01_uncertain_redispatch.json`
  - *Mechanism*: Task dispatched before crash enters `EXECUTION_UNCERTAIN`. Upstream router or supervisor stall detection sees lease dead, checks `!task.isCompleted()`, and initiates fallback dispatch on alternative worker. Second worker executes identical mutative action, causing dual concurrent writers, duplicate financial liability, and git branch corruption.
- **Proven Invariant**:
  $$\text{task.state} \in \{\text{EXECUTION\_UNCERTAIN}, \text{POSSIBLE\_SIDE\_EFFECT}\} \implies \text{AUTO\_REDISPATCH} = \text{BLOCKED}$$
  Any redispatch, retry, reroute, replan, or restart dispatch MUST be intercepted and rejected at a centralized choke point.
- **Windows Repair Concept**:
  - Centralized assertion at the gateway of `CourierDispatcher.dispatch()`.
  - Fail-closed evaluation: if uncertainty bit or side-effect marker is present, throw `SecurityBoundaryViolation` and force `HOLD_UNCERTAIN`.
- **Codex Classification**: `LIKELY_PRODUCTION_DEFECT` / `CONFIRMED_ARCHITECTURAL_REQUIREMENT` (P0).
- **Current Production Code Status**:
  - `PRODUCTION_CODE_CONFIRMED`: In `supervisor/reconciliation.js`, `EXECUTION_UNCERTAIN` is correctly tagged on leases, but Courier's central dispatch pipeline has no enforcement choke point preventing indirect caller modules (Supervisor, Resource Governor, Router) from reissuing the task.
- **Remaining Proof Gap**:
  - Zero Windows-level proof gaps.
  - Integration gap: Ensure transitive task dependency chains ($T_2$ depending on $T_1$) inherit uncertainty hold.

---

### 2. CANDIDATE L01: Hierarchical & Semantic Scope Locking
- **Candidate ID**: `DEFECT-L01`
- **Source Artifacts**:
  - `supervisor/no_stacking.js` (lines 21-59)
  - `supervisor/lease_manager.js` (lines 53-124)
  - `scratch/nightshift_adversarial_factory_v5/campaign_02_l01_no_stacking.js`
  - `scratch/final_4pct_adversarial_intervention_v1/REPAIRS/REPAIR-03-hierarchical-scope-checker.js`
- **Counterexample Artifact**:
  - `scratch/final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/L01_hierarchical_escape.json`
  - *Mechanism*: Worker 1 acquires lock on directory `src/`. Worker 2 requests lock on `src/core/auth/`. Because `no_stacking.js` only checks `task_id === task_id` and exact command string hashes, and lease manager lacks scope hierarchy, both acquire write leases concurrently, destroying working directory integrity.
- **Proven Invariant**:
  $$\forall S_1, S_2 \in \text{WriteScopes}: \text{CanonicalPrefix}(S_1) \cap \text{CanonicalPrefix}(S_2) \neq \emptyset \implies \text{MUTEX\_CONFLICT}$$
  Unrelated writers (e.g., `src/moduleA/` and `src/moduleB/`) MUST NOT be globally serialized, but hierarchical overlap MUST block.
- **Windows Repair Concept**:
  - Hybrid scope model supporting `tree:<path>`, `file:<path>`, `db:<table>`, `port:<num>`, `gitref:<ref>`.
  - Canonical path normalization with trailing slash (`path.normalize(p).replace(/\\/g, '/').replace(/\/$/, '') + '/'`).
  - Filesystem case-folding where applicable (Windows NTFS and default macOS APFS).
- **Codex Classification**: `LIKELY_PRODUCTION_DEFECT` (P0).
- **Current Production Code Status**:
  - `PRODUCTION_CODE_CONFIRMED`: In `supervisor/no_stacking.js`, `evaluateHeavyTaskSubmission()` only matches duplicate tasks on the exact same task ID. There is NO path hierarchy or declared resource collision check in active production code.
- **Remaining Proof Gap**:
  - Pure algorithmic path logic; zero Mac host requirement.

---

### 3. CANDIDATE G01: Deferred Liability & Capability Gate
- **Candidate ID**: `DEFECT-G01`
- **Source Artifacts**:
  - `money_factory/safety_gates.js` (lines 43-129)
  - `scratch/nightshift_adversarial_factory_v5/campaign_03_g01_human_gate.js`
  - `scratch/final_4pct_adversarial_intervention_v1/REPAIRS/REPAIR-04-fail-closed-intent-classifier.js`
- **Counterexample Artifact**:
  - `scratch/final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/G01_deferred_liability_bypass.json`
  - *Mechanism*: Autonomous agent signs up for "14-day free trial with auto-renew at €50/month" or "€0 due today under billing agreement". Naive check in `safety_gates.js` (`price_eur <= 0`) evaluates to true, bypassing human approval while incurring recurring financial liability.
- **Proven Invariant**:
  $$\text{Commitment} \in \{\text{RECURRING\_LIABILITY}, \text{AUTO\_RENEW}, \text{TERMS\_BINDING}, \text{PAYMENT\_AUTH}\} \implies \text{HUMAN\_GATE\_REQUIRED}$$
  $$\text{SemanticQualifier}(\text{InformationalPrefix}) \land \text{NoExecutionPayload} \implies \text{PASS\_WITHOUT\_GATE}$$
- **Windows Repair Concept**:
  - Dual-layer security: (1) NLP intent classification with grammatical negation handling, (2) Outbound tool/API capability enforcement intercepting billing/checkout endpoints regardless of prompt text.
  - Cryptographically bound single-use approval token schema.
- **Codex Classification**: `CONFIRMED_ARCHITECTURAL_REQUIREMENT` / `LIKELY_PRODUCTION_DEFECT` (P0).
- **Current Production Code Status**:
  - `PRODUCTION_CODE_CONFIRMED`: `money_factory/safety_gates.js` only checks immediate `price_eur > 0` and a static list of string verbs; deferred liability and tool-level capability traps are completely missing.
- **Remaining Proof Gap**:
  - Zero Mac host requirement.

---

### 4. CANDIDATE B01: Multi-Factor Process Identity & PID Wrap
- **Candidate ID**: `DEFECT-B01`
- **Source Artifacts**:
  - `supervisor/lease_manager.js` (lines 44-77)
  - `supervisor/reconciliation.js` (lines 43-65)
  - `scratch/nightshift_adversarial_factory_v5/campaign_04_b01_process_identity.js`
  - `scratch/final_4pct_adversarial_intervention_v1/REPAIRS/REPAIR-02-multifactor-process-tracker.js`
- **Counterexample Artifact**:
  - `scratch/final_4pct_adversarial_intervention_v1/COUNTEREXAMPLES/B01_pid_recycling_false_match.json`
  - *Mechanism*: Worker process PID 4120 exits. OS recycles PID 4120 to an unrelated daemon. Reconciler or Supervisor checks `kill(4120, 0)` or process table, observes PID alive, and either: (1) deadlocks waiting for task completion, or (2) assumes worker hung and issues `SIGKILL` against an innocent system process.
- **Proven Invariant**:
  $$\text{ProcessIdentity} = \langle \text{PID}, \text{StartTime}, \text{TaskToken}, \text{MachineId} \rangle$$
  $$\text{Evaluation}(\text{Identity}) = \text{UNKNOWN} \implies (\text{KILL\_ALLOWED} = \text{FALSE} \land \text{ASSUME\_ALIVE} = \text{FALSE})$$
- **Windows Repair Concept**:
  - Lease schema expanded to record `process_start_time` and `task_token`.
  - Process inspector returns tri-state enum: `MATCH_CONFIRMED`, `DEFINITE_MISMATCH`, `UNKNOWN`.
  - `UNKNOWN` strictly fails closed (neither kill nor assume alive).
- **Codex Classification**: `CONFIRMED_ARCHITECTURAL_REQUIREMENT` / `CONTRACT_AMBIGUITY` (P1).
- **Current Production Code Status**:
  - `PRODUCTION_CODE_CONFIRMED`: In `supervisor/reconciliation.js`, `fingerprintMatch` defaults to `true` if command is uninspectable, and does NOT check `start_time`.
- **Remaining Proof Gap**:
  - `MAC_NATIVE_PROOF_REQUIRED`: Darwin kernel `proc_pidinfo(pid, PROC_PIDTASKINFO)` start-time retrieval under Sandbox/SIP restrictions.
