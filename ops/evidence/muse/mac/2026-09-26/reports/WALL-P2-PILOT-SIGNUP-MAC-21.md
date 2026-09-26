# WALL-P2-PILOT-SIGNUP — draft MD (MUSE-MAC-21)

TASK_ID=WALL-P2-PILOT-SIGNUP
STATUS=DONE
WORKER=MUSE-MAC-21 · HOST=MAC · MODE=READ_ONLY · 2026-09-26T14:56Z
PREREQ=RV18_PILOT_ACCEPTANCE_TEST_MUSE02.md (peer MUSE-02, consumed not repeated).
No fake customers, no fake revenue, no implementation.

## Signup flow (manual onboarding, 3 steps, minutes not days)
STEP_1= Scope handshake. Customer names ONE project folder and ONE task type
  (from the RV06 workflow candidates). Operator records AUTHORIZED_WORKSPACE
  + AUTHORIZED_ACTIONS + REAL_GATES (RV17 model). No Courier internals shown.
STEP_2= Witness the acceptance test. Operator runs the RV18 test in front of
  the customer (~2 min, no server, no network, no credentials): timeout posts
  a visible FAILED record, follow-up claim refuses re-execution, restart
  relaunches once. Customer sees proof before paying anything. If any check
  prints FAIL, onboarding stops — the failure is the information.
STEP_3= First scoped run. Same task type as STEP_2, inside the authorized
  workspace, with the RV08 proof card delivered at the end. HUMAN_
  INTERVENTIONS count printed on the card; target 0 after the start command.

## Manual onboarding guide (operator checklist)
1. Confirm machine satisfies RV11 prep list (dependencies, state location,
   logs, recovery, uninstall path explained).
2. Set the two API keys (env or keychain — see PRIVACY-DATAFLOW draft);
   verify server refuses insecure defaults (live check, 1 min).
3. Run RV18 acceptance test WITH the customer watching. Record PASS/FAIL.
4. On PASS: authorize scope in writing (RV17 fields), run first scoped task,
   deliver proof card.
5. On FAIL: file RV13 incident card, do not proceed to paid scope.

## Rules
- No customer pays before STEP_2 prints PASS in front of them.
- "Signup" is a conversation + one witnessed test, not a form. No self-serve
  signup until GAP-1 (safe pytest) and GAP-5 (installer) are closed.
- Every signup produces exactly one evidence card (RV08 format) for the
  witnessed test — the customer's first artifact, free.

BLOCKER=NONE
NEXT=next pending P2 by wall priority
