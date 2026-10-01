# Courier Crew Idea Engine Prompt

Use only a small minority of free capacity for this mission.

COURIER CREW IDEA ENGINE

MODE=READ_ONLY_REPORT
HOST=AUTO
PROVIDER=AUTO
ROUND_HOURS=2

GOAL
Improve Courier's product/operations idea set without stealing capacity from the current proof path.

Read:
- ops/ai/COURIER_GROWTH_GOALS_2026-09-26.md
- ops/ai/COURIER_SESSION_STATE_2026-09-26.json
- docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md
- ops/ai/RETURNED_RESULT_POLICY.md

Rules:
- do not modify source
- do not create branches
- do not run heavy tests
- do not start servers/workers
- do not duplicate existing ideas
- do not promote an idea to proof
- do not create busywork
- do not expose secrets
- do not interrupt current final-candidate / RUN_1 / RUN_2 critical path

For each new idea require:
1. USER_PROBLEM
2. IDEA
3. WHY_BETTER
4. WHICH_EXISTING_GOAL_IT_EXTENDS
5. RISK
6. EVIDENCE_NEEDED
7. NOW/NEXT/LATER/NON_GOAL
8. DUPLICATE_CHECK
9. MINIMAL_PROOF
10. WHAT_NOT_TO_BUILD_YET

Prefer ideas that:
- reduce human relay
- improve truth/verification
- make 1..37 logical wall safer/faster
- reduce cost/quota waste
- improve restart/recovery
- simplify onboarding
- make status understandable to nontechnical users
- improve portability Mac/Windows/provider
- turn many agent reports into one reconciled next action

Visual friendliness is welcome:
🎯 goal
📜 ledger
🚀 ready
🧪 verify
✅ proven
🛡 guarded
💤 idle
🔥 pressure
💸 budget
🌍 larger product world

Return only the best 3 genuinely new ideas.

IDEA_1=
IDEA_2=
IDEA_3=
DUPLICATES_REJECTED=
CRITICAL_PATH_CHANGED=NO
NEXT_IDEA_AREA=

STOP.
