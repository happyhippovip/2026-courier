# PERMANENT "WEITER" CONTRACT — COURIER RC3 HARDENING LAB

This document records the user-defined contract for any bare continuation prompts (`weiter`, `continue`, `go on`, `mach weiter`) during this mission.

## INTERPRETATION RULE
Any bare continuation message must be interpreted ONLY as:
**CONTINUE THE CURRENT STAMPED WINDOWS RC3 LONG-RUN HARDENING LAB MISSION FROM DURABLE CURRENT_RESUME_CHECKPOINT.**

## STRICT NEGATIVE BOUNDARIES (NEVER AUTHORIZED)
A bare "weiter" is NOT authorization to:
- Start a new mission
- Change the primary goal
- Expand scope beyond this prompt
- Touch Mac host or files
- Access Mac host
- Transfer to Mac
- Modify frozen release `COURIER_HANDOFF_RC3`
- Touch `universuX`
- Commit
- Push
- Deploy
- Publish
- Spend money
- Send external messages
- Trade or interact with wallets
- Handle or request credentials
- Bypass any `HUMAN_GATE`
- Retry `EXECUTION_UNCERTAIN` work
- Weaken tests
- Create a second orchestrator

## EXECUTION PROTOCOL ON "WEITER"
1. Read filesystem/worktree truth.
2. Read `scratch/rc3_hardening_lab/CURRENT_RESUME_CHECKPOINT.md`.
3. Determine the current work package.
4. Do NOT repeat `VERIFIED` work.
5. Reconcile any `IN_FLIGHT` work before retrying.
6. Continue the `EXACT_NEXT_ACTION`.
7. Automatically continue through subsequent safe work packages.
8. Update the checkpoint as progress is made.
9. Stop only at:
   - Mission complete
   - Genuine `BLOCKED`
   - `HUMAN_GATE`
   - `EXECUTION_UNCERTAIN`
   - Prohibited boundary

## INVARIANTS
- Crash recovery: Do NOT start over.
- Completed packages: Do NOT repeat.
- Lease collision: `HOLD`. Do NOT stack.
- Unproven execution receipt: `EXECUTION_UNCERTAIN`. No redispatch.
