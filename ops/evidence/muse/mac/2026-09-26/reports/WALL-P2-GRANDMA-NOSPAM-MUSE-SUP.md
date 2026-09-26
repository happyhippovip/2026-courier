# WALL-P2 GRANDMA + NO-PERMISSION-SPAM website copy (PREP ONLY, no publish)

WORKER=muse-mac-support · HOST=MAC · MODE=READ_ONLY · 2026-09-26
SOURCES: CANONICAL_PRODUCT_PLAN ("externes Kernversprechen"), RV14 (short-answer-first),
RV02 (permission contract), RV03 (onboarding), landing draft MAC02.

## GRANDMA_EXPLANATION (3 levels, shortest-true-answer-first)
L1 (one sentence): "Es ist ein Programm, das angefangene Computerarbeit
selbstständig weiterführt — und fragt, bevor es etwas Wichtiges tut."
L2 (if asked): "Sie geben ihm eine Aufgabe. Es arbeitet sie Schritt für
Schritt ab, prüft jeden Schritt, und macht nach einer Pause genau dort weiter,
wo es aufgehört hat."
L3 (if asked): "Heute kann es das erst in Testläufen. Herunterladen kann man
noch nichts; wer es später ausprobieren will, trägt sich in die Pilotenliste ein."
CLAIM=understandability · CURRENTLY_PROVEN=N/A (copy, not capability) ·
SAFE_TO_PUBLISH_NOW=YES — contains zero capability claims beyond test runs.

## NORMAL_CUSTOMER (EN, website-ready draft)
"Courier picks up your work where you left off. Give it a task — it executes
each step, verifies the result, and continues with the next one. If your machine
restarts, it resumes instead of starting over. *Currently demonstrated in
supervised test runs; first customer pilots are being prepared.*"
CLAIM=A→VERIFY→B + resume · CURRENTLY_PROVEN=PARTIAL/NO (see FAQ Q1/Q2) ·
SAFE_TO_PUBLISH_NOW=YES only WITH the italic qualifier (mandatory, not optional).

## NO_PERMISSION_SPAM_EXPLANATION (website block, intent-labeled)
Headline: "Authorize once. Not every five minutes."
Copy: "You approve one project scope — which folder, which actions. Inside that
scope Courier works on its own. It comes back to you only for the things that
truly need a human: spending money, passwords, publishing, deleting, or
anything outside your scope."
CLAIM=scoped autonomy · CURRENTLY_PROVEN=NO (rule defined RV02, unenforced) ·
EVIDENCE=RV02/RV17 design docs · SAFE_TO_PUBLISH_NOW=YES only labeled
"how it will work" (intent), never as current behavior. Mandatory footnote:
"Permission model in design; developer builds currently confirm more often."

## MANUAL_ONBOARDING_FLOW (until packaging Gate 7 unlocks — no installer fiction)
1. Human operator clones the repo and checks out the released candidate hash.
2. Operator creates the customer workspace dir; records scope (folder + allowed actions) in one scope file the customer signs.
3. Operator runs the existing start command; customer watches the first task + proof card.
4. Customer receives: scope copy, evidence card of THEIR run, support contact.
SETUP_TIME_ASSUMPTION=~30 min operator-led (no self-service today).
CLAIM=onboarding path · CURRENTLY_PROVEN=PARTIAL (repo + run commands real;
scope file + evidence card per-run are prep docs) · SAFE_TO_PUBLISH_NOW=NO as
self-service; YES as "supervised pilot setup".
