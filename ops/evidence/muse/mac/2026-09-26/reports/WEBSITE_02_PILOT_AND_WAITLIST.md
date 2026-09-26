# WEBSITE_02: PILOT PROGRAM, ONBOARDING FLOW & WAITLIST SPECIFICATION

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Preparation Artifact  
**OUTPUT FILE**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/WEBSITE_02_PILOT_AND_WAITLIST.md`  
**GOVERNING PRINCIPLE**: Pilot agreements must define concrete, measurable success metrics. No fake customers or hypothetical enterprise logos.

---

## 1. Pilot Program Overview (`/pilot`)

The Courier Paid Pilot is a structured, 14-day technical engagement designed for software teams and engineering leads who want automated, unattended task execution without hallucination loops or permission fatigue.

### 1.1 The Pilot Contract (What We Measure)
Every pilot is evaluated against four strict binary criteria:

```
+──────────────────────────────────────────────────────────────────────────+
| THE FOUR PILOT ACCEPTANCE GATES                                          |
+───────────────────────────+──────────────────────────────────────────────+
| 1. FIRST-TRY SUCCESS      | Step A completes and outputs valid artifact  |
|                           | without manual parameter tweaking.           |
+───────────────────────────+──────────────────────────────────────────────+
| 2. INDEPENDENT VERIFY     | Step A artifact is checked and approved by   |
|                           | decoupled verifier before plan advances.     |
+───────────────────────────+──────────────────────────────────────────────+
| 3. ZERO-HUMAN ADVANCE     | Step B starts automatically in < 1 second.   |
|                           | HUMAN_RELAYS = 0 between steps.              |
+───────────────────────────+──────────────────────────────────────────────+
| 4. RESTART INTEGRITY      | Simulated mid-run reboot resumes cleanly.    |
|                           | Finished steps are NEVER re-executed.        |
+───────────────────────────+──────────────────────────────────────────────+
```
> **The Deal**: If any of these four criteria fails during the pilot workflow, the pilot is considered incomplete and refunded. That is the guarantee.

---

## 2. Waitlist / Pilot Application Form Fields

To ensure incoming pilot users match Courier's verified capabilities, the application form collects structured, deterministic requirements:

### Form Schema & Customer Prompts

```markdown
### Field 1: Technical Point of Contact
- Label: "Work Email"
- Type: Email (Required)
- Placeholder: `engineer@company.com`

### Field 2: Operating Environment
- Label: "Primary Execution Host"
- Type: Radio / Select (Required)
  - [x] macOS (Apple Silicon or Intel) — *Currently active pilot lane*
  - [ ] Windows 11 / Server 2022 — *In preparation (waitlist)*
  - [ ] Linux (Ubuntu 22.04+) — *In preparation (waitlist)*

### Field 3: Target Workflow Category
- Label: "What repeatable task would you like Courier to run?"
- Type: Select (Required)
  - ( ) Codebase Health & Dependency Audit (Static check -> Verify -> Fix PR)
  - ( ) Test Suite Gap Harvesting (Run tests -> Isolate failure -> Draft reproduction test)
  - ( ) API Integration Contract Sync (Fetch schema -> Generate stubs -> Verify compilation)
  - ( ) Migration Verification (Schema transform -> Sandboxed run -> Checksum compare)
  - ( ) Other bounded engineering task

### Field 4: Definition of Checkable Output
- Label: "How do you know when this task is truly done?"
- Type: Textarea (Required)
- Placeholder: "e.g. A new test file exists and passes pytest, or a JSON report with sha256 matches expected schema."
- Helper text: *"Courier requires an observable or deterministic artifact to verify before continuing."*

### Field 5: Safety & Scope Authorization
- Label: "Are you authorized to grant Single-Scope access to a local project directory?"
- Type: Checkbox (Required)
  - [ ] Yes, I can designate an isolated repository workspace for Courier.
```

---

## 3. Manual Onboarding Flow (3 Steps, 3 Clicks, < 3 Minutes)

The onboarding flow requires zero internal architectural comprehension.

```
[ Step 1: Select Scope ] ───► [ Step 2: Set Safety Gate ] ───► [ Step 3: Run Baseline ]
Pick 1 Project Folder          Confirm 0.00 EUR Budget Cap     Receive Verified Proof Card
```

### Detailed Onboarding Progression:
1. **Step 1: Scope Designation (1 Click)**
   - Screen prompt: *"Select the project folder where Courier is allowed to work."*
   - Customer action: Clicks `[ Choose Folder ]` -> selects `/Users/customer/projects/my-repo`.
   - Security assertion: Courier binds `AUTHORIZED_WORKSPACE` to this path. All other disks/folders are strictly inaccessible.
2. **Step 2: Safety & Budget Baseline (1 Click)**
   - Screen prompt: *"Confirm Safety Profile."*
   - Default settings pre-locked:
     - Cloud Spend Cap: **€0.00** (Zero external billing without explicit prompt).
     - Network Access: Localhost / Hermetic only.
     - Git Write Scope: Restricted to scratch branches (No `main` push).
   - Customer action: Clicks `[ Authorize Scope & Lock Boundaries ]`.
3. **Step 3: Verification Baseline Run (< 30 Seconds)**
   - System executes a hermetic health check on the selected repo (reads repo status, checks package dependencies, verifies build tools).
   - Verifier approves output; UI presents the first **Courier Proof Card**.
   - Result: Customer sees immediate, checkable evidence of local autonomy before running production tasks.

---

## 4. Pricing Experiment Copy & Commercial Terms

### 4.1 Paid Pilot Package Copy
> **"The 14-Day Engineering Pilot"**  
> **€500 / Project Workspace** *(Deposit-backed, 100% satisfaction guarantee)*

#### What is Included:
- **Dedicated Single-Scope Runner**: Configured for your macOS repository.
- **Up to 5 Customized Deterministic Workflows**: Bounded DAGs ($A \rightarrow \text{VERIFY} \rightarrow B$) tailored to your codebase.
- **Zero-Relay Verification Guarantee**: Verifier checks artifacts independently before unlocking downstream steps.
- **State Recovery Protection**: Workflow resumes seamlessly after machine sleep, reboot, or process crash.
- **Direct Engineer Support**: Dedicated Slack/Discord coordination channel with core developers.

#### The Commercial Truth:
- We do not sell "unlimited autonomous magic".
- We sell reliable, verifiable, crash-resilient task completion for software teams.
- If Courier cannot complete your chosen workflow unattended, you pay nothing.

---

## 5. Pilot & Onboarding Claim Discipline Registry

| Claim Element | Public Claim Statement | Currently Proven? | Evidence Source | Safe to Publish Now? |
| :--- | :--- | :---: | :--- | :---: |
| **PL-01** | Bounded 2-step workflows execute unattended | **YES** | `MUSE_A2B_EVIDENCE_CARD.md`, `tests/verify_restart_proof_deterministic.py` | **YES** (for macOS pilots) |
| **PL-02** | 3-step, 3-minute manual onboarding flow | **YES** | Specification in `RV03_CUSTOMER_ONBOARDING.md`, CLI initialization tests | **YES** (as onboarding guide) |
| **PL-03** | 100% money-back guarantee based on 4 criteria | **YES** | Commercial policy definition in `RV01_PAID_PILOT_PACKAGE.md` | **YES** |
| **PL-04** | Self-serve credit card checkout with Stripe billing | **NO** | Deferred platform feature (E30 triple dead / Product Shell locked) | **NO** (Use manual invoice/pilot agreement) |
| **PL-05** | Production Windows enterprise cluster support | **NO** | Schema drift documented in `MM11` / `results/E10-windows-portability.md` | **NO** (List as waitlist only) |
