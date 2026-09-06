# RESPONSE CONVERSION PLAYBOOK (11-STATE DETERMINISTIC ROUTER)

When an inbound reply arrives for any of the 6 active correlation IDs, execute the exact pre-approved conversion recipe:

---

## 1. POSITIVE_INTEREST ("Interested", "Let's do it", "Send invoice")
- **Action:** Stage immediate invoice via `PaymentAndInvoiceEngine` and send pre-approved onboarding instructions.
- **Turnaround SLA:** Response within 15 minutes.
- **Delivery Trigger:** Stage immediate ZIP download or report generation upon payment verification.

## 2. QUESTION ("How does it work?", "What do you need from us?")
- **Action:** Clarify in 2 sentences: (1) Zero access/credentials needed, (2) Output delivered within SLA.
- **Tone:** Technical, consultative, zero sales fluff.

## 3. SCOPE_REQUEST ("Can we add X?", "Does it cover repo Y?")
- **Action:** Bound scope strictly. Affirm what is included for the fixed price; offer add-on tier if beyond scope.

## 4. PRICE_OBJECTION ("Can you do a discount?")
- **Action:** Firm value defense. Sub-€100 pricing is already heavily subsidized for pilot evaluation.

## 5. NOT_NOW ("Check back next quarter")
- **Action:** Friendly acknowledgment. Set automated reminder trigger for 60 days out. Zero spam.

## 6. NOT_INTERESTED ("No thanks", "Pass")
- **Action:** Polite 1-sentence sign-off. Mark prospect `NOT_INTERESTED` in tracker. Never email again.

## 7. WRONG_PERSON ("Talk to Jane in Platform Engineering")
- **Action:** Thank them, route to designated contact with fresh personalized context.

## 8. BOUNCE (Mailer-Daemon, 550 User Unknown)
- **Action:** Immediately mark `BOUNCED` in tracker. Park experiment branch.

## 9. AUTO_REPLY (Out of office / Vacation)
- **Action:** Retain in `WAITING_FOR_RESPONSE`. Check expiration date on auto-responder.

## 10. UNSUBSCRIBE_OR_STOP ("Remove me", "Opt out")
- **Action:** Immediate opt-out. Add email to global suppression list. Zero follow-ups.

## 11. UNKNOWN
- **Action:** Route to Primary Executor for 1-time classification.
