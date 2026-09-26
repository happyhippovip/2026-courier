# PILOT-COMMERCIAL-02 — payment options + agreement inputs + follow-up (manual, no platform)

WORKER=MAC-02 (MUSE) · HOST=MAC · MODE=NON_CODE_PREP · 2026-09-26
Complements: PILOT-01 (fixed-fee-after-PASS rule), PRICING-EXPERIMENT (MAC10,
no real numbers), SUPPORT-FLOW (REAL_GATE money rule), RV17 (scope model).
No billing platform exists — everything here is human-executed. No fake revenue.

## PAYMENT_FLOW_OPTIONS (pick one per pilot, record the pick)
P-A. MANUAL_INVOICE_AFTER_PASS (default): operator sends a plain invoice after
the day-0 witnessed PASS; pilot runs days 1–10 only after payment OR written
payment promise — customer's choice, recorded. If RV18 prints FAIL: no invoice,
ever, for that scope (PILOT-01 rule, repeated here so the money rule lives
where money is handled).
P-B. NO_CHARGE_LEARNING_PILOT: explicitly free, explicitly labeled a learning
pilot (not a sale). Use for pilot #1–2 if charging would slow learning. The
label matters: a free pilot misremembered as a paid one corrupts the pricing
experiment (MAC10). Record which one it was.
P-C. DEFERRED_DECISION: run the witnessed test free (always free — the card is
"the customer's first artifact, free", SIGNUP rule); price conversation only
after PASS. Never name a figure before PASS — naming one creates an anchor
the proof has not earned.
FORBIDDEN in all options: auto-renewal, per-seat/per-task metering (nothing
exists to meter), card details collection (no payment path exists — collecting
them would be deceptive, TRUST doc), discounts for "AI training data" or any
other non-cash consideration (pilot #1–5 stay simple: cash or free).

## PILOT_AGREEMENT_INPUTS (one page, signed in writing before day 1)
Names + date. AUTHORIZED_WORKSPACE (exact path, RV17). AUTHORIZED_ACTIONS
(copied from scope handshake, plain words). FORBIDDEN_ACTIONS (from B5 +
RV17 defaults). REAL_GATES that apply (money/auth/publish/destruct/scope/
expansion/irreversible — tick only those in play). REVOCATION (who says
"Stopp", how — from B6). DURATION (PILOT-01 2-week window + dates).
PRICE_OPTION (P-A/B/C + figure or "free learning pilot"). SUCCESS_CRITERIA
reference (this pack's file 01, S1–S6). EVIDENCE (proof card per task, RV08;
incident card on failure, RV13). EXIT (either side stops any time; failed
acceptance = no invoice; inconclusive S3 = extend-once or close).
No legalese beyond this page for pilots 1–5; a lawyer reviews before pilot 6.

## FOLLOWUP_MESSAGE (templates, sent by the operator, plain words)
DAY-11 (evaluation opens): "Die zwei Wochen sind um. Anhand Ihrer Karte:
[Tasks] erledigt und geprüft, [N] mal mussten Sie eingreifen. Zwei Fragen:
(a) Wie viele Minuten brauchten Sie morgens nach einer über-Nacht-Fortsetzung?
(b) Würden Sie das für diese Aufgabe wieder einschalten? Ein Satz genügt."
DAY-14 (close): PASS close — "Alle sechs Kriterien stehen auf PASS. Die Karten
bleiben bei Ihnen. Wenn Sie weitermachen wollen, vereinbaren wir den nächsten
abgegrenzten Umfang — gleiche Regeln, neuer Zettel." / FAIL or INCONCLUSIVE
close — "Kriterium [Sx] steht auf [FAIL/INCONCLUSIVE]. Das ist das Ergebnis
des Piloten, keine Rechnung [falls P-A: für den Folgeumfang]. Der Fehlerbericht
bleibt bei Ihnen; wir melden uns, wenn [konkrete Lücke] geschlossen ist."
Rule: every follow-up quotes the customer's own B2 number back to them. Never
quote our hopes.
