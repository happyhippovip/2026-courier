# Courier Pilot Preparation Packet — 2026-09-27

**Status**: PILOT_READY / PRODUCT_PREPARATION  
**Authority**: GOOGLE_CLI (Read-Only Product Prep)  
**Reference Document**: [`docs/COURIER_USER_REPO_ONBOARDING_AND_IDEA_INTAKE_2026-09-27.md`](file:///Users/user/Downloads/2026-courier/docs/COURIER_USER_REPO_ONBOARDING_AND_IDEA_INTAKE_2026-09-27.md)  
**Boundaries**: Zero Product Shell modifications, zero customer fabrication, zero payment trigger.  

---

## 1. Candidate Selection Criteria

To ensure high-signal pilot verification without operational risk:

- **Ideal Candidate**: Technical or semi-technical project lead / developer maintaining an active GitHub repository.
- **Repository Characteristics**:
  - Clear automated verification (e.g. `pytest`, `npm test`, `cargo test`, or deterministic build scripts).
  - Clean modular architecture with localized feature or bugfix requirements.
  - Standard runtime (Python, Node/TypeScript, Go, Rust).
- **Disqualifying Characteristics**:
  - Closed-source proprietary binary blobs without source code.
  - Repositories lacking any automated testing or deterministic verification criteria.
  - Environments requiring complex custom hardware or manual physical testing.
- **Commitment Model**: User provisions access to a dedicated feature branch or fork (`courier-pilot/*`); production `main` branches are strictly write-protected.

---

## 2. Goal Contract Specification

Every pilot task must be governed by an immutable, human-confirmed Goal Contract:

```yaml
goal_contract:
  goal_id: "PILOT-GOAL-001"
  project_name: "example-project"
  repo_url: "github.com/user/example-project"
  target_branch: "courier-pilot/feature-x"
  objective: "Implement deterministic artifact validation and idempotency retry handling."
  acceptance_criteria:
    - "Automated test suite passes with exit code 0."
    - "Zero skipped tests (SKIPPED_COUNT=0)."
    - "Clean git diff with zero trailing whitespace (git diff --check)."
  allowed_scope:
    - "src/verifier/"
    - "src/contracts/"
    - "tests/"
  forbidden_scope:
    - ".github/workflows/"
    - "config/production.json"
    - "migrations/"
  budget_cap_usd: 10.00
  human_required_gates:
    - "SCHEMA_MIGRATION"
    - "BILLING_TIER_UPGRADE"
    - "DEPLOY_PRODUCTION"
```

---

## 3. Baseline Questionnaire (5 Minimal Questions)

Designed to collect 100% of required context in under 3 minutes without exposing internal agent concepts:

1. **Objective**: What exact feature, bugfix, or refactor do you want Courier to complete?
2. **Branching**: What is the base branch, and what dedicated pilot branch should Courier work on?
3. **Proof Command**: What single command (e.g. `pytest`, `npm test`) verifies that your code works?
4. **Scope Boundaries**: Are there any sensitive or off-limits files Courier must strictly NOT touch?
5. **Budget Limit**: What is the maximum compute/token budget (in USD) authorized for this goal?

---

## 4. Permission & Data Scope

- **Principle of Least Privilege**:
  - Courier operates strictly on isolated feature branches or forks (`courier-pilot/*`).
  - No direct commit access to default branches (`main` / `master`).
- **Cryptographic & Secret Hygiene**:
  - Zero storage or transmission of user account passwords, personal access tokens, or payment secrets.
  - Authentication handled via GitHub App / OAuth connector with revocable permissions.
  - Runtime environment secrets injected strictly via local `.env` runners outside git tracking.
- **Bounded Read Surface**:
  - Reads limited strictly to repository files within declared scope; zero scans of host machine.

---

## 5. Retention & Deletion Policy

- **Customer Data Ownership**:
  - All project artifacts, decisions, and proof records live in the user's repository (under `.courier/`).
  - The repository remains 100% functional and understandable even if Courier is disconnected.
- **Transient State Pruning**:
  - Intermediate worker logs, scratch files, and execution cache stored locally on runner are automatically deleted after 7 days.
- **Immediate Data Deletion**:
  - Upon user request or pilot completion, all local scratch directories, state caches, and temporary worker clones are completely wiped.

---

## 6. Setup, Support & Cost Capture

- **Zero-Friction Setup**:
  - Single lightweight runner script or standalone CLI (`courier run`).
  - Automatic environment detection (Python venv, Node modules).
- **Autonomous Support**:
  - Courier reports status asynchronously via markdown status files; no real-time human chat monitoring required.
- **Deterministic Cost Ledger**:
  - Token consumption and API calls tracked per goal:
    - Model/Provider calls logged with exact timestamp, token count, and dollar cost estimate.
    - Local CPU/deterministic checks recorded as $0.00 compute.
    - Automatic execution halt when `budget_cap_usd` threshold is reached.

---

## 7. HIPG / RSR / NDR Pilot Metrics

| Metric | Name | Definition | Pilot Target |
|---|---|---|---|
| **HIPG** | Human Intervention Per Goal | Number of times a human is prompted during execution | **0** (Confirm Goal once -> Done) |
| **RSR** | Run Success Rate | Percentage of goals verified PASS on first autonomous run | **> 90%** |
| **NDR** | No-Drift Rate | Percentage of edits strictly adhering to `allowed_scope` | **100%** |

---

## 8. Manual Repo Onboarding Step-by-Step Flow

```
[User Creates Branch: courier-pilot/xyz]
                  |
                  v
[User Fills 5-Question Questionnaire]
                  |
                  v
[Courier Generates Immutable Goal Contract]
                  |
                  v
[User Reviews & Confirms: CONFIRM=YES]
                  |
                  v
[Courier Runs Autonomous Execution Loop (Zero Relay)]
                  |
                  v
[Automated Verification: Tests Pass + Diff Clean]
                  |
                  v
[Courier Opens Pull Request with Attached Proof Card]
```

---

## 9. Pilot Status & Handoff

```ini
PILOT_PREPARATION_STATUS=COMPLETE
CORE_ENGINE_REQUIREMENT=Awaiting FINAL_SHA + Core Freeze
PRODUCT_SHELL_STATUS=UNTOUCHED (Per instructions)
CUSTOMER_ACCOUNTS=UNTOUCHED (No synthetic accounts created)
PAYMENT_SYSTEM=UNTOUCHED (Zero billing triggered)
```
