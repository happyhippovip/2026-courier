# PILOT-03 SUCCESS CRITERIA + PAYMENT FLOW + SETUP CHECKLIST (MUSE-MAC-21)

## SUCCESS_CRITERIA (measured day 14, all from proof cards + B-answers)
- S1 CONTINUITY: at least 3 next-day sessions where the customer resumed
  from the proof card/state WITHOUT manual reconstruction (B1 minutes -> ~0
  on those days). This is the key promise, measured — not asserted.
- S2 ZERO-UNEXPLAINED: HUMAN_INTERVENTIONS across all cards equals the
  counted, customer-approved gates only; every other card shows 0.
- S3 NO-DUPE/NO-LOSS: zero duplicate executions, zero lost results
  (E18 criteria applied to pilot tasks).
- S4 WITNESSED-BEFORE-PAID: day-0 acceptance PASS on record; any FAIL day
  voids the invoice for that scope, no discussion.
- PILOT PASSES if S1+S2+S3+S4 all hold. Partial = learning, not success.

## PAYMENT_FLOW_OPTIONS (manual only — no billing platform)
- Option A (default): invoice after day-14 evaluation, only if S4 held and
  customer confirms S1 value in writing (one sentence suffices).
- Option B: half after witnessed PASS (day 0), half after day 14. Offer only
  if customer requests staged commitment.
- Never: upfront full payment, auto-renewal, per-seat metering (nothing to
  meter with). Every charge: explicit approval + receipt + audit line.

## SETUP_CHECKLIST (operator, before day 0)
- [ ] Machine meets RV11 prep list (runtime, state location, logs, recovery,
      uninstall explained to customer).
- [ ] COURIER_API_KEY + COURIER_VERIFIER_API_KEY set (env or keychain);
      insecure-default refusal verified live; verifier key != worker key.
- [ ] Server binding decided deliberately (default 0.0.0.0:8080 is
      LAN-reachable — see privacy draft; localhost-only if pilot is local).
- [ ] Scope handshake recorded (workspace, actions, real gates, revocation).
- [ ] RV18 acceptance test rehearsed once WITHOUT customer (operator only).
- [ ] Proof-card delivery path agreed (where customer reads cards).
