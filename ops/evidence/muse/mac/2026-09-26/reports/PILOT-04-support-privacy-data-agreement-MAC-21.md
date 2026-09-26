# PILOT-04 SUPPORT/PRIVACY/DATA/AGREEMENT (MUSE-MAC-21, 2026-09-26)

Consumes WALL-P2-SUPPORT-FLOW + WALL-P2-PRIVACY-DATAFLOW drafts (not repeated).

## SUPPORT_BOUNDARIES
- Covered: triage by RV07 class with quoted policy; proof+incident cards
  attached to every response; business-hours response ("next working day").
- NOT covered: 24/7, uptime %, data recovery beyond durable state files,
  Windows hosts, third-party provider outages (quota/rate-limit pauses are
  explained, not compensated).

## PRIVACY_CHECKLIST (per pilot, operator ticks)
- [ ] Keys inventoried: where each lives (env/keychain), who can read them.
- [ ] Server binding recorded + customer-approved (LAN vs localhost).
- [ ] Credential-reference-only confirmed: no secret pasted into chats,
      tickets, or the channel registry (reference strings only).
- [ ] State/log locations shown to customer; retention + deletion on request.
- [ ] Publishing gate acknowledged: nothing external without explicit approval.
- [ ] Pilot-end deletion offered (state, logs, cards) with confirmation.

## DATA_PROCESSING_INVENTORY (what exists, where — evidence-gated)
- Task definitions + instructions: server state (central_state.json).
- Results + artifacts + hashes: server state + artifact store (per E04 lane).
- Verification records (verdicts, verifier ids): server state.
- Worker stdout: DISCARDED today (DEVNULL — GAP-4); tell the customer
  plainly: "we cannot show you live worker output yet; proof cards carry
  what was recorded."
- No customer data leaves the pilot machine except provider API calls the
  task itself requires (named per scope; each is a real gate if new).

## PILOT_AGREEMENT_INPUTS (fields for a one-page agreement, not legal advice)
PARTIES / SCOPE (workspace+actions) / GATES (real-gate list) / DURATION
(2 weeks) / PRICE (fixed, invoiced after witnessed PASS) / NO-INVOICE-ON-FAIL
clause / EVIDENCE (proof cards per task) / SUPPORT (boundaries above) /
PRIVACY (checklist above) / REVOCATION (one message stops everything;
deletion offered) / SIGNATURES + DATE.
