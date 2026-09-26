# WALL-P2-PILOT-OFFER — commercial core (MAC-04)

TASK_ID=WALL-P2-PILOT-OFFER · STATUS=DONE · WORKER=MAC-04 · HOST=MAC ·
MODE=READ_ONLY · 2026-09-26T15:51Z. No fake customers, no fake revenue, no
implementation. Complements (not repeats) WALL-P2-PILOT-SIGNUP-MAC-21.

## IDEAL_FIRST_PILOT_PROFILE
Solo developer or 2-5 person team with a small, repeatable, verifiable
computer chore they already do weekly: e.g. triaging a queue into done/
blocked with a written record; reconciling a download folder into named
places with a log; nightly status summaries from a fixed set of files.
Must have: ONE project folder they can name; tolerance for a 2-minute
witness test before paying; a human who can answer money/auth/publish
gates within a day. Must NOT be: regulated data, production deploys,
anything irreversible, anyone needing a dashboard on day one.

## PILOT_OFFER
"For two weeks, Courier does your one recurring chore inside one folder you
authorize. You start it once. It works, checks its own work, shows you a
proof card, and continues with the next round. You come back the next day
and see what got done and what is next -- without reconstructing anything
yourself. If it ever needs money, passwords, publishing, or anything
destructive, it stops and asks. That is the whole offer."

## PILOT_PRICE_EXPERIMENT
No fixed price yet -- run as experiments, first 5 pilots only:
(a) flat 3-day free run, then EUR 49 for the 2-week pilot, refunded if the
proof card ever shows HUMAN_INTERVENTIONS > 2 after the start command;
(b) EUR 0 + EUR 29 per completed verified week (max 2 weeks);
(c) team variant: EUR 149 flat for up to 5 people, same refund rule.
Record which variant each pilot takes and why they picked it. No annual
talk, no per-seat math, no discount ladders.

## PILOT_DURATION
2 weeks from first scoped run (STEP_3 of signup). Long enough for ~10
daily cycles (the promise is about "the next day"); short enough to stay a
pilot. Extension only as a second explicit pilot, never silent rollover.

## Key promise (kept narrow, provable)
"Courier brings you back to your work the next day without making you
reconstruct everything manually." Proven part (hermetic, localhost):
persisted fsync state + resume-retry + proof card with run history. NOT
promised: zero touch forever, cross-machine continuity, phone UI.
