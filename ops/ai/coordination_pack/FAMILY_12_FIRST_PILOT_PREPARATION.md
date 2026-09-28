# Family 12: First Pilot Operational Protocol & Metrics Specification

Status: COMPLETE
Principle: Non-code operational preparation while Central Writer finalizes candidate code.

---

## 1. Goal Contract Template

```yaml
GoalContract:
  contract_version: "2026-09-27.1"
  goal_id: "PILOT-GOAL-001"
  user_id: "pilot_user_alpha"
  goal_summary: "Execute multi-step workflow across overnight session without context loss"
  workflow_steps:
    - step_index: 1
      name: "Phase 1: Ingestion & Analysis"
      acceptance_criteria: "Produce structured summary artifact verified by SHA-256"
    - step_index: 2
      name: "Phase 2: Execution & Output Generation"
      acceptance_criteria: "Consume Phase 1 artifact and produce verified result"
  permitted_filesystem_paths:
    - "/Users/user/workspace/pilot_project"
  forbidden_actions:
    - "No destructive git commands (force-push, hard reset)"
    - "No secret or credential transmission"
    - "No uncontrolled external network calls"
  human_gate_trigger: "Ambiguous error, unknown file path, or budget limit reached"
```

---

## 2. Quantitative Pilot Metrics Definitions

| Metric | Full Name | Canonical Definition | Target Threshold |
|---|---|---|---|
| **HIPG** | Human Interventions Per Goal | $\frac{\text{Total Manual Human Interventions}}{\text{Completed Goals}}$ | $\le 0.2$ (at most 1 intervention per 5 goals) |
| **RSR** | Resume Success Rate | $\frac{\text{Successful Resumes Without State Loss}}{\text{Total Session Restarts}}$ | $\ge 95\%$ |
| **NDR** | Next-Day Return Score | First-cohort rating: "Did Courier bring you back exactly where you left off?" | $3\text{--}5$ (1st cohort), $2$ (2nd), $0\text{--}1$ (later) |
| **SETUP_MINUTES** | Time to First Goal | Minutes from downloading folder to first goal actively running | $\le 10\text{ minutes}$ |
| **SUPPORT_TIME** | Operator Help Required | Minutes of operator assistance required per pilot user per day | $\le 5\text{ minutes}$ |
| **PROVIDER_COST** | Token / API Cost per Goal | Dollar/Euro cost incurred across all models per completed goal | $\le \text{EUR } 0.50\text{ per goal}$ |

---

## 3. Pilot Checklists

### A. Pilot Start Checklist
1. Review and sign Data Scope & Privacy Checklist.
2. Clone repository / unpack folder.
3. Configure API key in `.env` (non-root, restricted scope).
4. Run `./courier start` or launch daemon.
5. Submit initial Goal Contract.
6. Verify status displays `ARBEITET`.

### B. Next-Day Return Question
> *"When you opened your computer this morning, was Courier in the exact state you expected, with all verified work preserved and your next step clearly presented?"*  
> Options: `[1: Lost context completely] ... [5: Exactly where I left off, zero friction]`

### C. Pilot End Checklist
1. Export complete Execution Ledger (`ops/ai/wall_ledger/ledger.jsonl`).
2. Tally total human intervention events.
3. Record total token spend.
4. Issue final Proof Card to user.
5. Securely remove temporary staging directories.
