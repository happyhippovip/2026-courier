# Courier Private Moat Kill

**PRIVATE / DO NOT PUBLISH.**

## 1. Behavioral Identity Envelope
* **BUYER:** Security teams, Red Teams.
* **PAIN:** Inability to fingerprint AI agent behavior across sessions.
* **ALTERNATIVE:** Log analysis, IP blocking.
* **COPY_RISK:** High. Upstream models can change behavior slightly, breaking the envelope.
* **UPSTREAM_RISK:** High. Providers might offer this natively.
* **PROPRIETARY_DATA:** None currently.
* **48H_KILL_TEST:** Can we fingerprint the current agent reliably within 48h?
* **VERDICT:** KILL. Too fragile, upstream risk is too high.

## 2. Evidence Surplus (Verification Market)
* **BUYER:** Compliance officers, AI auditors.
* **PAIN:** Need for independent verification of AI outcomes.
* **ALTERNATIVE:** Manual audits.
* **COPY_RISK:** Medium. Requires building a trusted verifier network.
* **UPSTREAM_RISK:** Low. Providers don't want to audit themselves.
* **PROPRIETARY_DATA:** The Ledger of proven outcomes.
* **48H_KILL_TEST:** Will a buyer pay EUR149 just for the cryptographic proof of a single task?
* **VERDICT:** KEEP OPEN. Test via Continuity Audit.

## 3. Actuation Escrow & Witness Routing
* **BUYER:** Enterprise IT, Risk Management.
* **PAIN:** Fear of agents taking destructive actions.
* **ALTERNATIVE:** Sandboxing, Human-in-the-loop.
* **COPY_RISK:** Low. Requires complex infrastructure.
* **UPSTREAM_RISK:** Medium.
* **PROPRIETARY_DATA:** None. Pure configuration.
* **48H_KILL_TEST:** Try to sell "Safe Escrow" vs "Fast Execution".
* **VERDICT:** KILL. Problem is configuration, not a distinct product moat right now.
