# 2026 Courier Operator Model

## 1. Core Operating Philosophy
- **Humans are IDEA GIVERS & GOAL SETTERS**: Humans define high-level strategic direction, objectives, priorities, constraints, and provide explicit decisions at human-only gates.
- **Agent System Provides Operational Execution**: Chief interprets human intent, Courier decomposes goals into missions, and the Capacity Router assigns tasks to the best execution engine (CLI1, Codex, Gemini/Antigravity).
- **Multi-Chat Input Consolidation**: Ideas and goals originating across multiple conversations or tools feed into ONE unified, coordinated Chief and Courier execution pipeline (no fragmented or competing plans).

## 2. Autonomous Execution & Continuation
- **Unattended Continuation on Safe Local Tasks**: Safe internal steps progress automatically without requiring repeated human confirmation ("weiter").
- **Strict Verification Cycle**:
  ```
  HUMAN GOAL -> CHIEF INTENT -> COURIER DECOMPOSITION -> ROUTER (CLI1/Codex/Gemini)
  -> LOCAL EXECUTION -> RESULT VERIFICATION -> FINGERPRINT LEDGER -> NEXT SAFE TASK
  ```

## 3. Mandatory Operating Invariants
- **TRUTH > SPEED**: All status reports and evidence must reflect verified repository and runtime truth. Fabricated or assumed success is strictly prohibited.
- **SINGLE_WRITER = YES**: Exactly one active writer holds the exclusive writer lease per workspace scope (`TaskLeaseManager`).
- **HEAVY_JOB_LIMIT = 1**: Heavy or long-running jobs are strictly limited to one concurrent slot across the system.
- **VERIFY_BEFORE_NEXT = YES**: Every task result must be verified before proceeding to the next dependent task.
- **NO ACCOUNT / QUOTA EVASION**: No automated bypassing of provider policies, account hopping, or unauthorized credential rotation.

## 4. Strict Human-Only Gates (Always Prohibited Autonomously)
Autonomous agents are strictly blocked and must yield to humans at all times for:
1. **Credentials & Authentication**: Login, OAuth flows, 2FA prompts, CAPTCHAs, secret/token management.
2. **Financial Operations**: Real spend (`AUTONOMOUS_SPEND_LIMIT_EUR = 0`), payment activation, live trading, wallet transaction signing.
3. **External Communications**: Public posting, social publication, customer contact, outbound email/SMS campaigns.
4. **Legal & Governance**: Terms of service acceptance, KYC compliance, account registration or deletion.

## 5. Computer-Does-The-Work Policy

**CORE PRINCIPLE:** The human must NOT become the terminal operator. For normal safe technical work, the computer does the work.

1. HUMAN_IS_NOT_TERMINAL_OPERATOR
2. SAFE_TERMINAL_COMMANDS_RUN_BY_AGENT=YES
3. SAFE_DIAGNOSTICS_RUN_BY_AGENT=YES
4. SAFE_REMOTE_COMMANDS_RUN_BY_AGENT=YES
5. SAFE_TESTS_RUN_BY_AGENT=YES
6. SAFE_RECOVERY_RUN_BY_AGENT=YES
7. RESULTS_RETURNED_TO_CONTROL_PLANE=YES
8. HUMAN_ACTION_ONLY_FOR_REAL_HUMAN_GATE=YES
9. NO_PROMPT_TRANSPORT_WHEN_AUTOMATION_CAN_DO_IT=YES
10. NO_MANUAL_WORKER_SELECTION_WHEN_ROUTER_CAN_DECIDE=YES

### Continuation Model
TASK
→ COMPUTER HEALTH CHECK
→ COMPUTER EXECUTION
→ COMPUTER VERIFY
→ COMPUTER RESULT
→ COMPUTER NEXT SAFE TASK

### Blocker Resolution
If a temporary technical blocker occurs:
→ computer diagnoses
→ performs bounded safe recovery
→ retries
→ checkpoints if unresolved
→ reports exact blocker

## 6. Multi-Agent Orchestration Plan
MULTI_AGENT_ORCHESTRATION_PLAN=8_STEPS
CURRENT_STEP=1
COMPUTER_DOES_THE_WORK=YES
HUMAN_PROMPT_TRANSPORT=NO
