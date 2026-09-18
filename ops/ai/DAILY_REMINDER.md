# DAILY REMINDER
PACKET FIRST. ONE WRITER. T0 → T1 → T2. T3 BEFORE CODEX.
BLOCKED TASK != BLOCKED PROJECT. LEDGER LAST. NO FAKE GREEN.

ZERO-HANG POLICY (status: POLICY unless noted IMPLEMENTED/VERIFIED):
- No generic killall. Every test-created process has owner_test_id,
  tracked PID, bounded lifetime, targeted cleanup.
- Target invariant: OWNED_CHILD_PROCESSES=0 after test completion.
