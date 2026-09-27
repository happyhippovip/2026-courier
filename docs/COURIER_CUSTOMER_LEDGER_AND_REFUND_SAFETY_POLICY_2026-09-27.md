# Courier Customer Ledger & Refund Safety Policy — 2026-09-27

Status: product/release guardrail. Public-safe. Does not replace legal/payment-provider advice.

## Principle

Customers should be able to understand what happened to their work and money, raise a complaint, and receive a traceable resolution or refund when policy permits.

Courier must never rely on hidden internal state to settle a customer dispute.

## Customer ledger included with the product

Every paid customer experience should eventually include access to a customer-facing ledger view/export covering the events relevant to that customer.

The customer ledger should be:
- readable in plain language
- based on the same underlying evidence as internal records
- privacy-filtered
- exportable
- append-only from the customer's perspective
- explicit about corrections/reversals rather than silently rewriting history

It should be able to show, where applicable:
- order/subscription/payment reference
- product/plan
- amount/currency as reported by the payment provider
- time
- service/task reference
- execution/proof reference
- refund/credit/dispute status
- support case reference
- final resolution

## Money-safety rules

1. Do not store raw card details, bank credentials, payment-provider secrets, or unnecessary payment payloads in the Courier ledger.
2. Use payment-provider-issued IDs/references for charges/refunds when possible.
3. A failed or ambiguous Courier execution must never silently consume a customer's entitlement/credit without a traceable record.
4. Refunds/credits must be explicit ledger events, never silent mutation of the original charge record.
5. Duplicate charge/refund protection must use provider idempotency keys / stable operation IDs where available.
6. Unknown payment state must display UNKNOWN/PENDING and reconcile with the payment provider; never guess success.
7. Customer-visible monetary claims must come from payment-provider evidence, not inferred internal counters.
8. No automatic refund implementation is authorized until payment-provider semantics and business policy are explicit.

## Complaint and refund workflow

Future minimum flow:

CUSTOMER_REQUESTED_REVIEW
-> SUPPORT_CASE_OPENED
-> EVIDENCE_ATTACHED
-> DECISION_PENDING
-> APPROVED_REFUND | APPROVED_CREDIT | DENIED_WITH_REASON
-> PROVIDER_REFUND_SUBMITTED where applicable
-> PROVIDER_CONFIRMED | PROVIDER_FAILED | PROVIDER_PENDING
-> CUSTOMER_NOTIFIED
-> CASE_CLOSED

Each transition should have:
- stable case_id
- customer/account reference
- relevant transaction/service references
- actor or automation identity
- timestamp
- reason
- evidence references
- previous state
- next state

## Evidence boundary

The ledger must distinguish:
- work reported
- work verified
- service delivered
- payment authorized
- payment captured
- refund requested
- refund approved
- refund submitted
- refund confirmed

These are different states. Never collapse them into one green "done".

## Customer rights / usability

The product should eventually give the customer:
- a simple transaction/service history
- complaint/report-problem action
- case status
- refund/credit status
- export/download of their own relevant ledger records
- a human-readable explanation of the final decision
- a clear route to human support for unresolved money issues

Do not expose internal prompts, secrets, private worker IDs, raw logs, or other customers' data.

## Internal engineering requirements

The ledger foundation should support future events for:
- billing reference attached
- entitlement granted/consumed/restored
- complaint opened
- evidence linked
- credit issued
- refund requested/submitted/confirmed/failed
- manual override with reason
- support resolution

These events are preparation only until the actual payment-provider integration exists.

## Release gate

Before paid public launch, require a separate payment/refund readiness review covering:
- provider integration
- idempotency
- duplicate-charge prevention
- refund semantics
- outage behavior
- reconciliation
- support ownership
- customer notification
- privacy/data retention
- applicable consumer/legal obligations

## Product promise boundary

Courier may promise traceability and a clear resolution path only after the relevant ledger/support/payment flow is implemented and tested.

No evidence -> no monetary PASS.
