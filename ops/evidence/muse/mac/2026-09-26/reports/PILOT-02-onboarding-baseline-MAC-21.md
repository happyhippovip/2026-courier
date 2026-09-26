# PILOT-02 ONBOARDING SCRIPT + BASELINE QUESTIONS (MUSE-MAC-21, 2026-09-26)

MODE=NON_CODE_PREP. Consumes WALL-P2-PILOT-SIGNUP-MAC-21.md (3-step flow) and
RV18 acceptance test (peer MUSE-02) — not repeated here, referenced.

## ONBOARDING_SCRIPT (operator reads/says, ~15 minutes)
1. "Show me the folder this work lives in and describe one task you repeat."
   -> Record AUTHORIZED_WORKSPACE + task type. (2 min)
2. "I will now run our acceptance test in front of you. It takes 2 minutes.
   PASS means: a timeout posts a visible FAILED record, a follow-up claim
   refuses to re-run it, and a restart relaunches exactly once."
   -> Run RV18 test. Read the four check lines aloud. (5 min)
3a. On PASS: "Scope confirmed. Your first scoped run starts [when]. After
   every task you get a proof card: result, verification, human-intervention
   count. Target: zero after this conversation." (3 min)
3b. On FAIL: "This is the information — the system is not ready for your
   scope today. This failure report is yours. We stop here, no invoice."
   -> File RV13 incident card, stop. (3 min)
4. Keys: "Two keys — one for doing work, one for checking it. They live in
   your environment or Mac keychain; we read them, never write secrets."
   (cf. PRIVACY-DATAFLOW draft.) (2 min)

## BASELINE_QUESTIONS (asked day 0, re-asked day 14 — the delta IS the pilot)
- B1: "Yesterday, how many minutes did reconstructing your work cost you?"
- B2: "Which recurring task would you most like to never reconstruct?"
- B3: "What does 'done' look like for one instance of that task?"
- B4: "What must NEVER happen without your explicit approval?" (feeds gates)
- B5: "Who else touches this work, and what breaks if they can't see state?"
- Record answers verbatim on day 0; day-14 evaluation compares B1 (minutes
  before/after) and B3 (was 'done' met per proof cards?).
