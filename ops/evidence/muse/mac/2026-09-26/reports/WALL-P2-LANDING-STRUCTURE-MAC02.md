# WALL-P2-LANDING-STRUCTURE — draft (evidence-gated copy, PREP ONLY)

WORKER=MAC-02 (MUSE) · HOST=MAC · MODE=READ_ONLY · 2026-09-26
Forbidden claims honored: no "zero-human operation", no "restart-proof",
no "installer exists". Every line below maps to cited evidence or is
labeled ASPIRATION (not yet proven).

## Page structure (static, 6 blocks)
1. HEADLINE + subline (value prop, §copy)
2. HOW IT WORKS — 3 steps, each with its evidence note
3. WHAT WE CAN SHOW TODAY — demo slot (feeds WALL-P2-DEMO-STORYBOARD)
4. HONEST LIMITS — what it does NOT do yet (mandatory block, never omitted)
5. PILOT — who it is for + what a pilot measures (feeds WALL-P2-PILOT-SIGNUP)
6. FAQ + PRIVACY pointers (feeds WALL-P2-FAQ, WALL-P2-PRIVACY-DATAFLOW)

## Copy (draft)
HEADLINE: "Software that finishes the second step on its own."
SUBLINE: "Courier executes a task, checks the result, and continues with
the next one — in isolated test runs, without a human relay between steps."
[EVIDENCE: GM5 canary A→VERIFY→B, HUMAN_RELAY=0 — fixture-scoped, see LIMITS.]

STEP 1 — DO: "Give it a task with a checkable result."
[EVIDENCE: deterministic fixtures with expected_sha256 — E04/E05, MMAC4.]
STEP 2 — CHECK: "It verifies its own result before continuing."
[EVIDENCE: hash-match verifier, PASS→RECONCILED transitions — GM5 mapping.
ASPIRATION for open-ended tasks: today's verifier only matches exact
expected hashes (GM5 clarification).]
STEP 3 — CONTINUE: "The next task starts by itself."
[EVIDENCE: current_step_index auto-increment observed in canary state — GM5.]

HONEST LIMITS (ship with the page, not behind a click):
- Proven only on deterministic, byte-predictable tasks — not on open work.
- Verification today = exact-hash comparison, not judgment (RV19/GAP2).
- No installer, no customer machine story yet (RV11 prep-only).
- The payment/customer path is not yet runnable (E30 triple dead).
- ASPIRATION, labeled as such: scoped autonomy without permission spam
  (design: RV02/RV17), customer-visible proof card (RV08), one-question
  human gates (grandma surface, ENTWURF — no UI built).

PILOT (copy): "A first pilot is one repeatable task with a checkable result,
run in isolation, measured by: done on first try, verified, continued alone,
recovered from restart. If any measure fails, the pilot fails — that is the deal."
[EVIDENCE NEED: restart-recovery of the PILOT run itself is P1 work owned by
WALL-P1-RESTART-MATRIX — do not pre-claim it here.]

STATUS=DRAFT_COMPLETE · no unproven claims · feeds 4 sibling P2 tasks
