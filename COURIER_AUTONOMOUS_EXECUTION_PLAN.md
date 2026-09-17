# Courier Autonomous Execution Plan

This is the durable remaining-work roadmap for Courier. It guides the unattended execution loop.

## Milestones

### 1. LEDGER/HANDOFF
- **Objective**: Establish the machine-readable, zero-chat handoff primitive.
- **Dependencies**: None.
- **Required Capabilities**: File write, Git.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Ledger file is parsable and verifiable.
- **Evidence Required**: agent_handoff_ledger.json exists with schema v2.
- **Safe Automatic Actions**: Initialize ledger, update state.
- **Forbidden Actions**: Tampering with current_sha.
- **Next Executable Action**: PR41 ACCEPTANCE

### 2. PR41 ACCEPTANCE
- **Objective**: Evaluate and integrate PR41 motor eligibility if writer lock allows.
- **Dependencies**: LEDGER/HANDOFF
- **Required Capabilities**: Git merge, Code analysis.
- **Required Authority**: None (requires Codex to yield).
- **Human Gates**: HUMAN_REQUIRED_MERGE (if active writer collision).
- **Money Gates**: None.
- **Acceptance Predicates**: Code integrated securely.
- **Evidence Required**: Git SHA of integration.
- **Safe Automatic Actions**: Check ownership, verify PR.
- **Forbidden Actions**: Unattended merge while Codex owns it.
- **Next Executable Action**: RELEASE

### 3. RELEASE
- **Objective**: Prepare the release candidate for public distribution.
- **Dependencies**: LEDGER/HANDOFF (and PR41 if ready)
- **Required Capabilities**: Shell, Build tools.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Release builds cleanly.
- **Evidence Required**: Build artifacts.
- **Safe Automatic Actions**: Build, test.
- **Forbidden Actions**: Publishing untested artifacts.
- **Next Executable Action**: PUBLIC DEPLOYMENT

### 4. PUBLIC DEPLOYMENT
- **Objective**: Deploy the public Courier site.
- **Dependencies**: RELEASE
- **Required Capabilities**: GitHub Actions, API.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: HUMAN_REQUIRED_PUBLIC_REPO_VISIBILITY
- **Money Gates**: None (unless Pages fails on private).
- **Acceptance Predicates**: Deployment triggered successfully.
- **Evidence Required**: Actions run ID or branch update.
- **Safe Automatic Actions**: Trigger workflows, push to gh-pages.
- **Forbidden Actions**: None.
- **Next Executable Action**: PUBLICATION VERIFICATION

### 5. PUBLICATION VERIFICATION
- **Objective**: Verify that the deployed site is publicly reachable.
- **Dependencies**: PUBLIC DEPLOYMENT
- **Required Capabilities**: HTTP Client.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: HTTP 200 on public URL, contact email present.
- **Evidence Required**: HTTP Response body.
- **Safe Automatic Actions**: curl URL, parse response.
- **Forbidden Actions**: Assuming deployment pass without checking.
- **Next Executable Action**: PILOT INTAKE

### 6. PILOT INTAKE
- **Objective**: Prepare intake processing for pilot inquiries.
- **Dependencies**: PUBLICATION VERIFICATION
- **Required Capabilities**: Email/Form processing setup.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Configured intake forms or endpoints.
- **Evidence Required**: Config JSON for intake processing.
- **Safe Automatic Actions**: Generate JSON configs, save defaults.
- **Forbidden Actions**: Sending unsolicited emails, fake contact data.
- **Next Executable Action**: SALES PACKAGE

### 7. SALES PACKAGE
- **Objective**: Produce the sales collateral and pilot qualification requirements.
- **Dependencies**: PILOT INTAKE
- **Required Capabilities**: Markdown, File write.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Collateral files exist and are finalized.
- **Evidence Required**: Markdown files containing sales details.
- **Safe Automatic Actions**: Draft collateral.
- **Forbidden Actions**: External sales messages.
- **Next Executable Action**: FIRST PILOT

### 8. FIRST PILOT
- **Objective**: Onboard the first pilot customer.
- **Dependencies**: SALES PACKAGE
- **Required Capabilities**: Intake execution.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: HUMAN_REQUIRED_CUSTOMER_AGREEMENT
- **Money Gates**: None.
- **Acceptance Predicates**: Customer agrees to terms.
- **Evidence Required**: Intake ID and agreement record.
- **Safe Automatic Actions**: Parse intake responses, prepare onboard record.
- **Forbidden Actions**: Fake prospects.
- **Next Executable Action**: PAYMENT ONLY WHEN ACTUALLY REQUIRED

### 9. PAYMENT ONLY WHEN ACTUALLY REQUIRED
- **Objective**: Collect pilot payment from the onboarded customer.
- **Dependencies**: FIRST PILOT
- **Required Capabilities**: Payment Gateway API.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: MONEY_REQUIRED_PAYMENT_GATEWAY
- **Acceptance Predicates**: Payment processed successfully.
- **Evidence Required**: Transaction ID.
- **Safe Automatic Actions**: Read API response for transaction status.
- **Forbidden Actions**: Buying/configuring payment providers, auto-spend.
- **Next Executable Action**: POST-PILOT HARDENING

### 10. POST-PILOT HARDENING
- **Objective**: Harden systems after pilot execution.
- **Dependencies**: PAYMENT ONLY WHEN ACTUALLY REQUIRED
- **Required Capabilities**: Refactoring, Testing.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Zero severe bugs.
- **Evidence Required**: Audit report.
- **Safe Automatic Actions**: Audit code, run tests, apply fixes.
- **Forbidden Actions**: Destructive broad cleanup.
- **Next Executable Action**: NONE
