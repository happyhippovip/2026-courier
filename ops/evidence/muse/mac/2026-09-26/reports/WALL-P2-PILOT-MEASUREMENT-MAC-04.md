# WALL-P2-PILOT-MEASUREMENT — success criteria + baseline (MAC-04)

TASK_ID=WALL-P2-PILOT-MEASUREMENT · STATUS=DONE · WORKER=MAC-04 · HOST=MAC ·
MODE=READ_ONLY · 2026-09-26T15:51Z. No numbers invented; thresholds are
decision rules for the pilot review, not claims.

## BASELINE_QUESTIONS (ask BEFORE the first scoped run, write answers down)
1. What exact chore, in which folder, how often? (names the scope)
2. How long does it take you today, and what part is annoying? (pain anchor)
3. What does "done right" look like -- what would you check? (acceptance seed)
4. Who answers money/password/publish questions, and how fast? (gate latency)
5. What must Courier NEVER touch? (forbidden list, read back for confirmation)
6. How will you look at results -- same folder, email, chat? (proof channel)

## SUCCESS_CRITERIA (all must hold at day 14, else pilot = inconclusive)
- The chore ran >= 8 of 10 working days without operator restart.
- Every run produced a proof card (task, result, verifier, interventions).
- HUMAN_INTERVENTIONS after the start command <= 2 total (else refund per offer).
- Zero writes outside AUTHORIZED_WORKSPACE (audit: state diff + file log).
- Zero repeats of already-completed work (no duplicate execution observed).
- Customer answers "I did not reconstruct anything manually" unprompted
  when asked what mornings felt like (qualitative, recorded verbatim).
- At least one real gate occurred (money/auth/publish/destructive) AND
  Courier stopped and asked instead of proceeding (gates must be exercised,
  not just documented).

## PAYMENT_FLOW_OPTIONS (pick one per pilot, keep manual)
(a) Invoice after day 14 only if SUCCESS_CRITERIA hold, else free + refund
rule from offer. (b) EUR 49 upfront held, released on success, returned on
inconclusive. No cards stored, no subscriptions, no billing platform in
pilot phase -- a bank transfer and an email receipt suffice.
