# Courier Autonomous Execution Plan

This is the durable remaining-work roadmap for Courier. It guides unattended execution while Motor remains the sole runtime scheduler.

## Canonical execution policy: MAXIMUM SAFE PARALLELISM

Courier optimizes for **verified useful progress per unit time**, not for token burn, agent count, or chat activity.

- Continuously compute the complete safe executable frontier, not only the next single task.
- Dispatch independent, non-overlapping scopes concurrently to all legitimately available and authorized workers when Motor eligibility, capabilities, authority, and resource ownership allow it.
- Mac Antigravity, Windows Antigravity, Google CLI, and future authorized workers may execute concurrently. Provider identity is worker metadata, never workflow truth.
- One writer per logical scope/resource. Never create concurrency by allowing overlapping writers.
- A busy worker, provider wait, quota/session end, human gate, money gate, or writer collision blocks only its causally affected scope. Unrelated safe work continues.
- Prefer the cheapest sufficient worker/model for deterministic bounded work; use the strongest available worker where it materially increases verified throughput or resolves hard blockers.
- Reuse valid evidence and minimal context packages. Do not spend tokens rebuilding context that is already durable.
- Worker/session replacement is normal: CHECKPOINT -> PUSH -> CLEAN OWNED PROCESSES -> YIELD. A fresh authorized worker reconstructs from canonical repository/Ledger state, not old chat.
- Do not automate account rotation, quota circumvention, or provider-limit evasion. Multiple legitimately authorized workers/accounts may be used manually or through provider-supported mechanisms only within their terms and limits.
- No LLM polling, fake background loops, second scheduler, second queue, or second truth store. Motor remains the sole runtime scheduler/claim authority; Ledger remains coordination/evidence/handoff.
- No auto-spend, payment-provider signup, unattended merge, credential/security-control bypass, unsolicited external sales messages, fake PASS, or destructive broad cleanup.
- Native OS/provider scheduling or background-agent facilities may only wake/start the canonical Courier continuation/Motor path; they must not decide Courier task ownership themselves.
- Success metric: maximize causally verified completed tasks/hour while preserving acceptance, safety, ownership, and reproducibility.

### Frontier invariants

The continuation path must satisfy these behaviors:

1. blocked scope + independent work => continue independent work
2. writer collision + unrelated work => continue unrelated work
3. money gate + free work => continue free work
4. provider unavailable/busy + another eligible worker => dispatch to eligible worker
5. multiple independent eligible tasks/workers => execute concurrently when resources do not collide
6. stale or invalid Ledger => fail closed for affected claims; do not fabricate state
7. all remaining scopes genuinely blocked/completed => CLEAN_IDLE / true global stop

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
- **Required Authority**: None (requires Codex to yield/reassignment under canonical ownership rules).
- **Human Gates**: HUMAN_REQUIRED_MERGE (if active writer collision genuinely requires human resolution).
- **Money Gates**: None.
- **Acceptance Predicates**: Code integrated securely.
- **Evidence Required**: Git SHA of integration and causally relevant acceptance evidence.
- **Safe Automatic Actions**: Check ownership, verify PR; continue unrelated scopes while blocked.
- **Forbidden Actions**: Unattended merge while another writer owns it.
- **Next Executable Action**: RELEASE

### 3. RELEASE
- **Objective**: Prepare the release candidate for public distribution.
- **Dependencies**: LEDGER/HANDOFF (and PR41 only where causally required)
- **Required Capabilities**: Shell, Build tools.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Release builds cleanly.
- **Evidence Required**: Build/test evidence.
- **Safe Automatic Actions**: Build, test.
- **Forbidden Actions**: Publishing untested artifacts.
- **Next Executable Action**: PUBLIC DEPLOYMENT

### 4. PUBLIC DEPLOYMENT
- **Objective**: Deploy the public Courier site.
- **Dependencies**: RELEASE
- **Required Capabilities**: GitHub Actions, API.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: HUMAN_REQUIRED_PUBLIC_REPO_VISIBILITY only if genuinely required.
- **Money Gates**: None unless an unavoidable paid action is causally required.
- **Acceptance Predicates**: Deployment completes successfully; triggering alone is not proof.
- **Evidence Required**: Terminal workflow/deployment result and deployment identity.
- **Safe Automatic Actions**: Trigger authorized free workflows and inspect terminal result.
- **Forbidden Actions**: Auto-spend; marking publication proven from trigger/local build alone.
- **Next Executable Action**: PUBLICATION VERIFICATION

### 5. PUBLICATION VERIFICATION
- **Objective**: Verify that the deployed site is publicly reachable.
- **Dependencies**: PUBLIC DEPLOYMENT
- **Required Capabilities**: HTTP Client.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Public URL responds successfully and configured contact destination is present.
- **Evidence Required**: Actual public HTTP response/equivalent causal deployment evidence.
- **Safe Automatic Actions**: Request URL, parse response.
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
- **Evidence Required**: Config/evidence for intake processing.
- **Safe Automatic Actions**: Generate configs, save authorized defaults.
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
- **Evidence Required**: Versioned sales/pilot collateral.
- **Safe Automatic Actions**: Draft/refine collateral.
- **Forbidden Actions**: External sales messages without authorization.
- **Next Executable Action**: FIRST PILOT

### 8. FIRST PILOT
- **Objective**: Prepare and onboard the first real pilot customer.
- **Dependencies**: SALES PACKAGE
- **Required Capabilities**: Intake execution.
- **Required Authority**: Google-Antigravity.
- **Human Gates**: HUMAN_REQUIRED_CUSTOMER_AGREEMENT only when a real customer's agreement/action is required.
- **Money Gates**: None before money actually needs to be collected.
- **Acceptance Predicates**: Real customer agrees to applicable terms.
- **Evidence Required**: Real intake/agreement record.
- **Safe Automatic Actions**: Parse real intake responses, prepare onboarding record/package.
- **Forbidden Actions**: Fake prospects, unsolicited outreach, fabricated agreement.
- **Next Executable Action**: PAYMENT ONLY WHEN ACTUALLY REQUIRED

### 9. PAYMENT ONLY WHEN ACTUALLY REQUIRED
- **Objective**: Collect pilot payment when a real agreed transaction actually requires it.
- **Dependencies**: FIRST PILOT
- **Required Capabilities**: Authorized payment mechanism.
- **Required Authority**: Explicitly authorized payment action.
- **Human Gates**: As required by the real payment/account setup.
- **Money Gates**: MONEY_REQUIRED_PAYMENT_GATEWAY only at the first action genuinely requiring payment collection/setup.
- **Acceptance Predicates**: Payment mechanism/action is real and authorized.
- **Evidence Required**: Appropriate transaction/setup evidence without exposing secrets.
- **Safe Automatic Actions**: Read already-authorized status/evidence where available.
- **Forbidden Actions**: Buying/configuring payment providers or spending without explicit authorization.
- **Next Executable Action**: POST-PILOT HARDENING

### 10. POST-PILOT HARDENING
- **Objective**: Harden systems after pilot execution.
- **Dependencies**: Relevant pilot evidence; unrelated safe hardening may run earlier when independent.
- **Required Capabilities**: Refactoring, Testing.
- **Required Authority**: Google-Antigravity or another eligible authorized worker.
- **Human Gates**: None for safe internal work.
- **Money Gates**: None.
- **Acceptance Predicates**: Defined hardening acceptance predicates pass; do not use vague perfection claims.
- **Evidence Required**: Audit/test report.
- **Safe Automatic Actions**: Audit code, run tests, apply owned safe fixes.
- **Forbidden Actions**: Destructive broad cleanup.
- **Next Executable Action**: NONE when the full frontier is genuinely complete/blocked.
