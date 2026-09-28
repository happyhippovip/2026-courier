# Family 12: First Pilot Preparation & Operations

**Status**: READY FOR NON-CODE PILOT COHORT  
**Reference**: `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md` (Gate 5)

---

## 1. Goal Contract Template for Pilot

```markdown
# Courier Symphony — Goal Contract
- **GOAL_ID**: goal-pilot-[cohort]-[user_id]
- **GOAL_TEXT**: [Exact natural language description of user goal]
- **TARGET_SURFACE**: [Local workspace path / repository]
- **AUTHORIZED_CAPABILITIES**: [e.g. read_only_analysis, file_creation, test_execution]
- **BUDGET_CAP_EUR**: 10.00
- **MAX_ATTEMPTS_PER_TASK**: 3
- **HUMAN_GATE_CONDITIONS**:
  - File deletions or overwrites
  - External network API requests
  - Ambiguous recovery state
- **ACCEPTANCE_CRITERIA**:
  1. [Specific deliverable 1 with expected artifact path]
  2. [Specific deliverable 2 with verified test passing]
- **USER_CONFIRMATION**: [Explicit user opt-in before start]
```

---

## 2. Canonical Metrics Definitions

1. **HIPG (Human Interventions Per Goal)**:
   $$\text{HIPG} = \frac{\text{Total Human Prompts / Interventions}}{\text{Completed Goals}}$$
   *Pilot Target*: $\text{HIPG} \le 1.0$ (Goal entry + optional final sign-off; zero mid-flight relay).

2. **RSR (Restart Success Rate)**:
   $$\text{RSR} = \frac{\text{Successful Resumes after Session / Machine Restart}}{\text{Total Interrupted Goals}}$$
   *Pilot Target*: $\ge 90\%$.

3. **NDR (Next-Day Retention / Return Ratio)**:
   *Measurement*: Did the user return the next morning and resume exactly where they left off?
   *Threshold*: 3–5 users in first cohort; minimum 2 active returns next day.

4. **Operational Measurements**:
   - `SETUP_MINUTES`: Target $\le 15\text{ min}$ for manual onboarding.
   - `SUPPORT_EFFORT`: Logged in minutes per pilot user.
   - `PROVIDER_COST`: Tracked in EUR via token counter.
   - `HUMAN_INTERVENTION_LOG`: Structured log of every human interaction.
