# PILOT-04 AGREEMENT INPUTS + FOLLOWUP + DEMO-TO-PILOT CONVERSION (MUSE-02, 2026-09-26)

MODE=NON_CODE_PREP. No fake customers, no fake revenue, no billing platform, no Product Shell.
Consumes: PILOT-01 (offer), PILOT-02 (baseline B1-B5), PILOT-03 (success/payment/setup), RV07 (failure policy), RV08 (proof card), RV14 (plain-language rule). Nothing repeated, only referenced.

## DEMO_TO_PILOT_CONVERSION_FLOW (same visit or next day, ~30 min total)
1. Run the RV18 acceptance test witnessed (~2 min). Any FAIL → stop, hand over the failure report, no pitch. A failed demo that tells the truth converts better than a staged pass.
2. Ask B1+B2 (baseline pain + task to never reconstruct). If no recurring task exists → no pilot (say so; walk away).
3. Map their task to one RV06 workflow type live, in their words. If it doesn't fit cleanly → no pilot.
4. State the PILOT-01 offer verbatim (2 weeks, scoped, proof card per task, no invoice if acceptance FAILs). Name the fixed fee and the manual-invoice-after-PASS term.
5. Fill PILOT_AGREEMENT_INPUTS below together (15 min). Both sides sign/date the one page.
6. Schedule day-14 evaluation now (calendar invite before leaving).

## PILOT_AGREEMENT_INPUTS (one page, plain language, fill-in blanks)
- PARTIES: operator name + customer name/date.
- WORKSPACE: exact folder path (AUTHORIZED_WORKSPACE). Outside it = no touch without new written ok.
- TASK TYPE: one RV06 type in customer words + what "done" looks like (B3 answer).
- GATES (B4 answer): list of actions needing explicit approval (money, passwords, publishing, delete, irreversible). Everything else runs autonomously inside workspace.
- DURATION: 14 days from ___ to ___; evaluation meeting date/time fixed now.
- FEE: fixed ___; invoiced manually AFTER witnessed PASS; zero if acceptance FAILs. No tiers/seats/metering.
- EVIDENCE: proof card (RV08) per task incl. HUMAN_INTERVENTIONS count; failure handling per RV07 (quote the class, not new promises).
- DATA: what Courier reads/writes (PILOT privacy dataflow); customer may revoke workspace access any time → work parks, state handed over.
- SUPPORT: humans answer; every reply attaches proof card + incident card + last verified state.
- EXIT: either side stops with one message; customer keeps all artifacts + proof cards + state export.
- NOT PROMISED (initialed): no SLA, no 24/7, no Windows, no compliance certification, no "production-ready" claim.

## FOLLOWUP_MESSAGE (send within 24h of signing, and day 13 before evaluation)
Template (fill [brackets], keep under 120 words):
"Thanks — your pilot is set: [task type] in [folder], [date]–[date]. Our promise: you come back the next day without reconstructing anything — the proof card shows what ran, what was checked, and how often a human stepped in. If anything looks off, reply in plain words and we'll attach exactly what happened plus how it resumes. Evaluation: [date/time]. Nothing to install, nothing to learn."
Day-13 nudge: same + "please re-answer B1 (minutes reconstructing yesterday) so we can compare with day 0."
